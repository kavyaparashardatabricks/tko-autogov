"""Column sensitivity classifier.

Implements a model-endpoint interface so the backing model can be swapped
from a foundation model to a fine-tuned endpoint without changing the rest
of the pipeline.
"""

import json
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Sequence

from openai import OpenAI

from ..config import get_oauth_token, get_workspace_host, get_serving_endpoint

logger = logging.getLogger(__name__)

VALID_LABELS = {"pii", "pci", "confidential", "time_sensitive", "public"}

SYSTEM_PROMPT = """\
You are a data governance classifier. For each database column described below,
determine which sensitivity labels apply. Return ONLY a JSON array of objects,
one per column, with exactly these fields:
  - "column_name": the column name as given
  - "labels": array of applicable labels from: pii, pci, confidential, time_sensitive, public
  - "confidence": a float 0-1 indicating your confidence

Rules:
- pii: personally identifiable information (name, email, phone, SSN, address, DOB, IP, etc.)
- pci: payment card data (card number, CVV, expiry, cardholder name, bank account)
- confidential: business-sensitive data (salary, revenue, trade secrets, internal IDs)
- time_sensitive: data that should expire or have time-bounded access (session tokens, OTP, temp credentials)
- public: non-sensitive data

A column can have multiple labels. If clearly non-sensitive, return ["public"].
Do NOT include any text outside the JSON array.
"""


@dataclass
class ColumnClassification:
    table_catalog: str
    table_schema: str
    table_name: str
    column_name: str
    labels: list[str] = field(default_factory=list)
    confidence: float = 0.0
    model_name: str = ""
    model_version: str = ""


class BaseClassifier(ABC):
    @abstractmethod
    def classify(self, columns: Sequence[dict]) -> list[ColumnClassification]:
        """Classify a batch of column dicts and return classifications."""
        ...


class LLMClassifier(BaseClassifier):
    """Calls a Databricks Foundation Model (OpenAI-compatible) endpoint."""

    BATCH_SIZE = 60

    def __init__(self, endpoint: str | None = None):
        self.endpoint = endpoint or get_serving_endpoint()

    def _get_client(self) -> OpenAI:
        host = get_workspace_host()
        token = get_oauth_token()
        return OpenAI(api_key=token, base_url=f"{host}/serving-endpoints")

    def classify(self, columns: Sequence[dict]) -> list[ColumnClassification]:
        if not columns:
            return []

        all_results: list[ColumnClassification] = []
        for i in range(0, len(columns), self.BATCH_SIZE):
            batch = columns[i : i + self.BATCH_SIZE]
            all_results.extend(self._classify_batch(batch))
        return all_results

    def _classify_batch(self, columns: Sequence[dict]) -> list[ColumnClassification]:
        descriptions = []
        for col in columns:
            fqn = f"{col['table_catalog']}.{col['table_schema']}.{col['table_name']}"
            desc = (
                f"Table: {fqn}, Column: {col['column_name']}, "
                f"Type: {col.get('data_type', 'unknown')}"
            )
            comment = col.get("column_comment", "")
            if comment:
                desc += f", Comment: {comment}"
            descriptions.append(desc)

        user_content = "\n".join(descriptions)

        client = self._get_client()
        response = client.chat.completions.create(
            model=self.endpoint,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_content},
            ],
            max_tokens=4096,
            temperature=0.1,
        )

        raw = response.choices[0].message.content.strip()
        return self._parse_response(raw, columns)

    def _parse_response(
        self, raw: str, columns: Sequence[dict]
    ) -> list[ColumnClassification]:
        try:
            if raw.startswith("```"):
                raw = raw.split("\n", 1)[1].rsplit("```", 1)[0]
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            logger.warning("LLM returned unparseable JSON; marking all as public")
            parsed = []

        result_map: dict[str, dict] = {}
        for item in parsed:
            name = item.get("column_name", "")
            result_map[name] = item

        results = []
        for col in columns:
            match = result_map.get(col["column_name"], {})
            raw_labels = match.get("labels", ["public"])
            labels = [l for l in raw_labels if l in VALID_LABELS] or ["public"]
            results.append(
                ColumnClassification(
                    table_catalog=col["table_catalog"],
                    table_schema=col["table_schema"],
                    table_name=col["table_name"],
                    column_name=col["column_name"],
                    labels=labels,
                    confidence=float(match.get("confidence", 0.5)),
                    model_name=self.endpoint,
                    model_version="foundation-v1",
                )
            )
        return results


def get_classifier() -> BaseClassifier:
    """Factory: returns the active classifier implementation."""
    return LLMClassifier()
