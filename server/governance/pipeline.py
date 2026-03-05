"""Orchestration pipeline: scan -> diff -> classify -> apply (if agent) -> persist."""

import uuid
import logging
from datetime import datetime, timezone
from dataclasses import asdict

from ..config import get_workspace_client
from .. import db
from .scan import scan_columns
from .diff import compute_diff
from .classify import get_classifier, ColumnClassification
from .tags_policies import (
    apply_tags,
    apply_column_masks,
    apply_row_filters,
    apply_time_based_filters,
    ensure_governance_udfs,
)
from .groups import list_workspace_groups

logger = logging.getLogger(__name__)


async def run_pipeline(
    catalog: str | None,
    mode: str,
    group_names: list[str] | None = None,
) -> dict:
    """Execute the full governance pipeline.

    Args:
        catalog: Specific catalog name, or None for all catalogs.
        mode: "suggest" or "agent".
        group_names: Workspace group names to use for RBAC row filters.

    Returns:
        Summary dict with run_id and results.
    """
    run_id = str(uuid.uuid4())[:12]
    started_at = datetime.now(timezone.utc)
    client = get_workspace_client()

    catalogs_label = catalog or "__all__"

    await db.insert_trail({
        "run_id": run_id,
        "started_at": started_at,
        "catalogs": catalogs_label,
        "mode": mode,
    })

    # 1. Scan
    logger.info("[%s] Scanning columns (catalog=%s)", run_id, catalogs_label)
    current = scan_columns(client, catalog)
    logger.info("[%s] Found %d columns", run_id, len(current))

    # 2. Load memory & diff
    memory = await db.load_memory(catalog)
    diff = compute_diff(current, memory)
    logger.info("[%s] Diff: %s", run_id, diff.summary())

    await db.update_trail(run_id, changes_detected=diff.summary())

    # 3. Classify new + updated columns
    columns_to_classify = diff.new + diff.updated
    classifications: list[ColumnClassification] = []

    if columns_to_classify:
        logger.info("[%s] Classifying %d columns", run_id, len(columns_to_classify))
        classifier = get_classifier()
        classifications = classifier.classify(columns_to_classify)

        # Persist classifications
        cls_records = []
        for cls in classifications:
            cls_records.append({
                "run_id": run_id,
                "table_catalog": cls.table_catalog,
                "table_schema": cls.table_schema,
                "table_name": cls.table_name,
                "column_name": cls.column_name,
                "predicted_labels": cls.labels,
                "confidence": cls.confidence,
                "model_name": cls.model_name,
                "model_version": cls.model_version,
            })
        await db.insert_classifications(cls_records)

    # Build suggestions
    suggestions = _build_suggestions(classifications)
    await db.update_trail(run_id, suggestions=suggestions)

    # Store notification candidates for PII/PCI findings (deferred delivery)
    pii_pci_notifications = []
    for cls in classifications:
        sensitive = [l for l in cls.labels if l in ("pii", "pci")]
        if sensitive:
            fqn = f"{cls.table_catalog}.{cls.table_schema}.{cls.table_name}.{cls.column_name}"
            pii_pci_notifications.append({
                "run_id": run_id,
                "column_fqn": fqn,
                "labels": sensitive,
            })
    await db.insert_notification_candidates(pii_pci_notifications)

    # 4. Apply (agent mode only)
    applied_actions: list[dict] = []
    if mode == "agent" and classifications:
        logger.info("[%s] Agent mode: applying tags and policies", run_id)

        # Resolve groups if not provided
        if group_names is None:
            ws_groups = list_workspace_groups(client)
            group_names = [g["display_name"] for g in ws_groups]

        # Ensure governance UDFs exist
        catalog_set = set()
        for cls in classifications:
            catalog_set.add(cls.table_catalog)
        for cat in catalog_set:
            ensure_governance_udfs(client, cat)

        applied_actions.extend(apply_tags(client, classifications))
        applied_actions.extend(apply_column_masks(client, classifications))
        applied_actions.extend(
            apply_row_filters(client, classifications, group_names)
        )
        applied_actions.extend(
            apply_time_based_filters(client, classifications)
        )

    await db.update_trail(
        run_id,
        applied=applied_actions,
        finished_at=datetime.now(timezone.utc),
        notification_status="ready" if pii_pci_notifications else "deferred",
    )

    # 5. Update memory with full current snapshot
    await db.upsert_memory(current)
    if diff.deleted:
        await db.delete_memory(diff.deleted)

    return {
        "run_id": run_id,
        "catalog": catalogs_label,
        "mode": mode,
        "columns_scanned": len(current),
        "diff": diff.summary(),
        "classifications_count": len(classifications),
        "suggestions": suggestions,
        "applied": applied_actions,
        "pii_pci_candidates": len(pii_pci_notifications),
    }


def _build_suggestions(classifications: list[ColumnClassification]) -> list[dict]:
    suggestions = []
    for cls in classifications:
        non_public = [l for l in cls.labels if l != "public"]
        if not non_public:
            continue
        fqn = f"{cls.table_catalog}.{cls.table_schema}.{cls.table_name}.{cls.column_name}"
        suggestion: dict = {
            "column": fqn,
            "labels": cls.labels,
            "confidence": cls.confidence,
            "recommended_actions": [],
        }
        if set(cls.labels) & {"pii", "pci"}:
            suggestion["recommended_actions"].append("column_mask")
            suggestion["recommended_actions"].append("tag")
        if "confidential" in cls.labels:
            suggestion["recommended_actions"].append("row_filter")
            suggestion["recommended_actions"].append("tag")
        if "time_sensitive" in cls.labels:
            suggestion["recommended_actions"].append("time_based_filter")
            suggestion["recommended_actions"].append("tag")
        suggestions.append(suggestion)
    return suggestions
