"""Scan Unity Catalog information_schema to build a column snapshot."""

import hashlib
from databricks.sdk import WorkspaceClient


def _fingerprint(row: dict) -> str:
    parts = "|".join(
        str(row.get(k, ""))
        for k in ("table_catalog", "table_schema", "table_name",
                   "column_name", "data_type", "column_comment")
    )
    return hashlib.sha256(parts.encode()).hexdigest()[:16]


def scan_columns(client: WorkspaceClient, catalog: str | None = None) -> list[dict]:
    """Return a list of column records from information_schema.

    Each record has: table_catalog, table_schema, table_name, column_name,
    data_type, column_comment, fingerprint.
    """
    if catalog:
        query = f"""
            SELECT table_catalog, table_schema, table_name,
                   column_name, data_type, comment AS column_comment
            FROM `{catalog}`.information_schema.columns
            WHERE table_schema != 'information_schema'
            ORDER BY table_catalog, table_schema, table_name, ordinal_position
        """
    else:
        query = """
            SELECT table_catalog, table_schema, table_name,
                   column_name, data_type, comment AS column_comment
            FROM system.information_schema.columns
            WHERE table_schema != 'information_schema'
            ORDER BY table_catalog, table_schema, table_name, ordinal_position
        """

    result = client.statement_execution.execute_statement(
        statement=query,
        warehouse_id=_get_warehouse_id(client),
        wait_timeout="120s",
    )

    columns: list[str] = [
        c.name for c in (result.manifest.schema.columns or [])
    ]

    records = []
    for row_data in (result.result.data_array or []):
        row = dict(zip(columns, row_data))
        row["column_comment"] = row.get("column_comment") or ""
        row["fingerprint"] = _fingerprint(row)
        records.append(row)
    return records


def list_catalogs(client: WorkspaceClient) -> list[str]:
    catalogs = client.catalogs.list()
    return sorted(c.name for c in catalogs if c.name != "system")


def _get_warehouse_id(client: WorkspaceClient) -> str:
    """Pick the first available SQL warehouse."""
    warehouses = list(client.warehouses.list())
    for wh in warehouses:
        if wh.state and wh.state.value in ("RUNNING", "STARTING"):
            return wh.id
    if warehouses:
        return warehouses[0].id
    raise RuntimeError("No SQL warehouse available in this workspace")
