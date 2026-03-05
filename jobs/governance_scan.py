"""Scheduled job entrypoint for the Finance Governance pipeline.

Run as a Databricks Job (notebook task or script task) on a schedule.
Requires environment variables:
  DATABRICKS_HOST, DATABRICKS_TOKEN (or profile)
  PGHOST, PGPORT, PGDATABASE, PGUSER

Optional env:
  GOVERNANCE_CATALOG  - specific catalog to scan (default: all)
  GOVERNANCE_MODE     - "suggest" or "agent" (default: "agent")
"""

import asyncio
import json
import os
import sys
import logging

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from server import db
from server.governance.pipeline import run_pipeline

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


async def main():
    catalog = os.environ.get("GOVERNANCE_CATALOG") or None
    mode = os.environ.get("GOVERNANCE_MODE", "agent")

    logger.info("Initializing Lakebase schema...")
    await db.init_schema()

    logger.info("Starting governance scan (catalog=%s, mode=%s)", catalog, mode)
    result = await run_pipeline(catalog=catalog, mode=mode)

    logger.info("Run complete: %s", json.dumps(result, indent=2, default=str))
    return result


if __name__ == "__main__":
    asyncio.run(main())
