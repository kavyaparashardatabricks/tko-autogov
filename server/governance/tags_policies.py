"""Apply Unity Catalog tags, ABAC column masks, and RBAC row filters."""

import logging
from databricks.sdk import WorkspaceClient

from .classify import ColumnClassification
from .scan import _get_warehouse_id

logger = logging.getLogger(__name__)

GOVERNANCE_SCHEMA = "governance_udfs"

TAG_KEY = "sensitivity"

LABEL_TO_TAG_VALUE = {
    "pii": "PII",
    "pci": "PII",
    "confidential": "CONFIDENTIAL",
    "time_sensitive": "HIGHLYSENSITIVE",
    "public": None,
}

# ---------------------------------------------------------------------------
# Tag application via SQL (ALTER TABLE ... ALTER COLUMN ... SET TAGS)
# ---------------------------------------------------------------------------


def apply_tags(
    client: WorkspaceClient,
    classifications: list[ColumnClassification],
) -> list[dict]:
    """Apply sensitivity tags to columns in Unity Catalog. Returns applied actions."""
    applied = []
    wh_id = _get_warehouse_id(client)

    for cls in classifications:
        non_public = [l for l in cls.labels if l != "public"]
        if not non_public:
            continue

        fqn = f"`{cls.table_catalog}`.`{cls.table_schema}`.`{cls.table_name}`"
        applied_values: set[str] = set()
        for label in non_public:
            tag_value = LABEL_TO_TAG_VALUE.get(label)
            if not tag_value or tag_value in applied_values:
                continue
            applied_values.add(tag_value)
            stmt = (
                f"ALTER TABLE {fqn} ALTER COLUMN `{cls.column_name}` "
                f"SET TAGS ('{TAG_KEY}' = '{tag_value}')"
            )
            try:
                _exec(client, wh_id, stmt)
                applied.append({
                    "action": "tag",
                    "column": f"{fqn}.{cls.column_name}",
                    "tag_key": TAG_KEY,
                    "tag_value": tag_value,
                })
            except Exception as e:
                logger.error("Failed to apply tag on %s.%s: %s",
                             fqn, cls.column_name, e)
                applied.append({
                    "action": "tag_error",
                    "column": f"{fqn}.{cls.column_name}",
                    "error": str(e),
                })
    return applied


# ---------------------------------------------------------------------------
# UDF bootstrap: create governance UDFs in a shared schema
# ---------------------------------------------------------------------------


def ensure_governance_udfs(client: WorkspaceClient, catalog: str):
    """Create the governance UDF schema and helper UDFs if they don't exist."""
    wh_id = _get_warehouse_id(client)

    _exec(client, wh_id,
          f"CREATE SCHEMA IF NOT EXISTS `{catalog}`.`{GOVERNANCE_SCHEMA}`")

    # PII/PCI column mask: replaces value with '***REDACTED***' for users
    # not in the 'data_governance_admins' group.
    _exec(client, wh_id, f"""
        CREATE OR REPLACE FUNCTION `{catalog}`.`{GOVERNANCE_SCHEMA}`.mask_sensitive(val STRING)
        RETURNS STRING
        RETURN CASE
            WHEN is_account_group_member('data_governance_admins') THEN val
            ELSE '***REDACTED***'
        END
    """)

    # Time-based access UDF: returns true if current time is within
    # business hours (UTC 08:00-18:00, weekdays).
    _exec(client, wh_id, f"""
        CREATE OR REPLACE FUNCTION `{catalog}`.`{GOVERNANCE_SCHEMA}`.is_business_hours()
        RETURNS BOOLEAN
        RETURN (
            extract(HOUR FROM current_timestamp()) BETWEEN 8 AND 17
            AND dayofweek(current_date()) BETWEEN 2 AND 6
        )
    """)


# ---------------------------------------------------------------------------
# ABAC column masks
# ---------------------------------------------------------------------------


def apply_column_masks(
    client: WorkspaceClient,
    classifications: list[ColumnClassification],
) -> list[dict]:
    """Apply column mask policies for PII/PCI columns."""
    applied = []
    wh_id = _get_warehouse_id(client)

    sensitive_labels = {"pii", "pci"}
    for cls in classifications:
        if not (set(cls.labels) & sensitive_labels):
            continue

        fqn = f"`{cls.table_catalog}`.`{cls.table_schema}`.`{cls.table_name}`"
        mask_fn = f"`{cls.table_catalog}`.`{GOVERNANCE_SCHEMA}`.mask_sensitive"

        stmt = (
            f"ALTER TABLE {fqn} ALTER COLUMN `{cls.column_name}` "
            f"SET MASK {mask_fn}"
        )
        try:
            _exec(client, wh_id, stmt)
            applied.append({
                "action": "column_mask",
                "column": f"{fqn}.{cls.column_name}",
                "mask_function": mask_fn,
            })
        except Exception as e:
            logger.error("Failed to apply column mask on %s.%s: %s",
                         fqn, cls.column_name, e)
            applied.append({
                "action": "column_mask_error",
                "column": f"{fqn}.{cls.column_name}",
                "error": str(e),
            })
    return applied


# ---------------------------------------------------------------------------
# RBAC row filters by workspace group
# ---------------------------------------------------------------------------


def apply_row_filters(
    client: WorkspaceClient,
    classifications: list[ColumnClassification],
    group_names: list[str] | None = None,
) -> list[dict]:
    """Apply row-level security filters based on workspace groups.

    For tables that contain confidential columns, restrict row access
    to members of specified groups.
    """
    applied = []
    wh_id = _get_warehouse_id(client)

    if not group_names:
        return applied

    confidential_labels = {"confidential", "pii", "pci"}
    seen_tables: set[str] = set()

    for cls in classifications:
        if not (set(cls.labels) & confidential_labels):
            continue

        fqn = f"`{cls.table_catalog}`.`{cls.table_schema}`.`{cls.table_name}`"
        if fqn in seen_tables:
            continue
        seen_tables.add(fqn)

        catalog = cls.table_catalog
        ensure_row_filter_udf(client, catalog, group_names)

        filter_fn = f"`{catalog}`.`{GOVERNANCE_SCHEMA}`.row_access_filter"
        stmt = f"ALTER TABLE {fqn} SET ROW FILTER {filter_fn} ON ()"
        try:
            _exec(client, wh_id, stmt)
            applied.append({
                "action": "row_filter",
                "table": fqn,
                "filter_function": filter_fn,
                "groups": group_names,
            })
        except Exception as e:
            logger.error("Failed to apply row filter on %s: %s", fqn, e)
            applied.append({
                "action": "row_filter_error",
                "table": fqn,
                "error": str(e),
            })
    return applied


def ensure_row_filter_udf(
    client: WorkspaceClient,
    catalog: str,
    group_names: list[str],
):
    """Create or replace a row filter UDF that checks group membership."""
    wh_id = _get_warehouse_id(client)
    _exec(client, wh_id,
          f"CREATE SCHEMA IF NOT EXISTS `{catalog}`.`{GOVERNANCE_SCHEMA}`")

    group_checks = " OR ".join(
        f"is_account_group_member('{g}')" for g in group_names
    )

    _exec(client, wh_id, f"""
        CREATE OR REPLACE FUNCTION `{catalog}`.`{GOVERNANCE_SCHEMA}`.row_access_filter()
        RETURNS BOOLEAN
        RETURN (
            is_account_group_member('data_governance_admins')
            OR {group_checks}
        )
    """)


# ---------------------------------------------------------------------------
# Time-based row filter
# ---------------------------------------------------------------------------


def apply_time_based_filters(
    client: WorkspaceClient,
    classifications: list[ColumnClassification],
) -> list[dict]:
    """Apply time-based row filters for time_sensitive columns."""
    applied = []
    wh_id = _get_warehouse_id(client)

    seen_tables: set[str] = set()
    for cls in classifications:
        if "time_sensitive" not in cls.labels:
            continue

        fqn = f"`{cls.table_catalog}`.`{cls.table_schema}`.`{cls.table_name}`"
        if fqn in seen_tables:
            continue
        seen_tables.add(fqn)

        catalog = cls.table_catalog
        ensure_governance_udfs(client, catalog)

        filter_fn = f"`{catalog}`.`{GOVERNANCE_SCHEMA}`.is_business_hours"
        stmt = f"ALTER TABLE {fqn} SET ROW FILTER {filter_fn} ON ()"
        try:
            _exec(client, wh_id, stmt)
            applied.append({
                "action": "time_filter",
                "table": fqn,
                "filter_function": filter_fn,
            })
        except Exception as e:
            logger.error("Failed to apply time filter on %s: %s", fqn, e)
            applied.append({
                "action": "time_filter_error",
                "table": fqn,
                "error": str(e),
            })
    return applied


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _exec(client: WorkspaceClient, wh_id: str, stmt: str):
    result = client.statement_execution.execute_statement(
        statement=stmt,
        warehouse_id=wh_id,
        wait_timeout="50s",
    )
    if result.status and result.status.state:
        state_val = result.status.state.value if hasattr(result.status.state, 'value') else str(result.status.state)
        if state_val == "FAILED":
            error_msg = ""
            if result.status.error:
                error_msg = getattr(result.status.error, 'message', str(result.status.error))
            raise RuntimeError(f"SQL statement failed: {error_msg}\nStatement: {stmt[:200]}")
