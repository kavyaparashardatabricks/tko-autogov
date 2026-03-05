"""Diff current column scan against Lakebase memory to find new/updated/deleted."""

from dataclasses import dataclass, field


@dataclass
class DiffResult:
    new: list[dict] = field(default_factory=list)
    updated: list[dict] = field(default_factory=list)
    deleted: list[dict] = field(default_factory=list)

    @property
    def has_changes(self) -> bool:
        return bool(self.new or self.updated or self.deleted)

    def summary(self) -> dict:
        return {
            "new_count": len(self.new),
            "updated_count": len(self.updated),
            "deleted_count": len(self.deleted),
        }


def _key(row: dict) -> tuple:
    return (
        row["table_catalog"],
        row["table_schema"],
        row["table_name"],
        row["column_name"],
    )


def compute_diff(current: list[dict], memory: list[dict]) -> DiffResult:
    mem_map = {_key(m): m for m in memory}
    cur_map = {_key(c): c for c in current}

    result = DiffResult()

    for key, cur_row in cur_map.items():
        mem_row = mem_map.get(key)
        if mem_row is None:
            result.new.append(cur_row)
        elif mem_row.get("fingerprint") != cur_row.get("fingerprint"):
            result.updated.append(cur_row)

    for key, mem_row in mem_map.items():
        if key not in cur_map:
            result.deleted.append(mem_row)

    return result
