import os
import json
from typing import Optional
from datetime import datetime, timezone

import asyncpg

from .config import get_oauth_token

_pool: Optional[asyncpg.Pool] = None

MEMORY_TABLE = "column_memory"
TRAIL_TABLE = "run_trail"
CLASSIFICATION_TABLE = "classification_results"
NOTIFICATION_TABLE = "notification_candidates"

# In-memory fallback when no Lakebase is attached
_mem_memory: dict[str, dict] = {}        # keyed by (cat.schema.table.col)
_mem_trails: list[dict] = []
_mem_classifications: list[dict] = []
_mem_notifications: list[dict] = []


async def get_pool() -> Optional[asyncpg.Pool]:
    global _pool
    if _pool is not None:
        return _pool

    if not os.environ.get("PGHOST"):
        return None

    token = get_oauth_token()
    _pool = await asyncpg.create_pool(
        host=os.environ["PGHOST"],
        port=int(os.environ.get("PGPORT", "5432")),
        database=os.environ["PGDATABASE"],
        user=os.environ["PGUSER"],
        password=token,
        ssl="require",
        min_size=2,
        max_size=10,
    )
    return _pool


async def refresh_pool():
    """Recreate pool with a fresh OAuth token (tokens expire after ~1 hour)."""
    global _pool
    if _pool:
        await _pool.close()
        _pool = None
    await get_pool()


async def init_schema():
    """Create Lakebase tables if they do not exist."""
    pool = await get_pool()
    if pool is None:
        print("WARNING: PGHOST not set – skipping schema init. Attach a Lakebase database resource.")
        return
    async with pool.acquire() as conn:
        await conn.execute(f"""
            CREATE TABLE IF NOT EXISTS {MEMORY_TABLE} (
                table_catalog   TEXT NOT NULL,
                table_schema    TEXT NOT NULL,
                table_name      TEXT NOT NULL,
                column_name     TEXT NOT NULL,
                data_type       TEXT,
                column_comment  TEXT,
                fingerprint     TEXT NOT NULL,
                last_seen_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                PRIMARY KEY (table_catalog, table_schema, table_name, column_name)
            )
        """)

        await conn.execute(f"""
            CREATE TABLE IF NOT EXISTS {TRAIL_TABLE} (
                run_id              TEXT PRIMARY KEY,
                started_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                finished_at         TIMESTAMPTZ,
                catalogs            TEXT NOT NULL,
                mode                TEXT NOT NULL,
                changes_detected    JSONB,
                suggestions         JSONB,
                applied             JSONB,
                notification_status TEXT NOT NULL DEFAULT 'deferred'
            )
        """)

        await conn.execute(f"""
            CREATE TABLE IF NOT EXISTS {CLASSIFICATION_TABLE} (
                id              SERIAL PRIMARY KEY,
                run_id          TEXT NOT NULL,
                table_catalog   TEXT NOT NULL,
                table_schema    TEXT NOT NULL,
                table_name      TEXT NOT NULL,
                column_name     TEXT NOT NULL,
                predicted_labels JSONB NOT NULL,
                confidence      REAL,
                model_name      TEXT,
                model_version   TEXT,
                created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        """)

        await conn.execute(f"""
            CREATE TABLE IF NOT EXISTS {NOTIFICATION_TABLE} (
                id          SERIAL PRIMARY KEY,
                run_id      TEXT NOT NULL,
                column_fqn  TEXT NOT NULL,
                labels      JSONB NOT NULL,
                status      TEXT NOT NULL DEFAULT 'pending',
                created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        """)


# ---------------------------------------------------------------------------
# Memory helpers
# ---------------------------------------------------------------------------

async def load_memory(catalog: str | None = None) -> list[dict]:
    pool = await get_pool()
    if pool is None:
        rows = list(_mem_memory.values())
        if catalog:
            rows = [r for r in rows if r.get("table_catalog") == catalog]
        return rows
    async with pool.acquire() as conn:
        if catalog:
            rows = await conn.fetch(
                f"SELECT * FROM {MEMORY_TABLE} WHERE table_catalog = $1", catalog
            )
        else:
            rows = await conn.fetch(f"SELECT * FROM {MEMORY_TABLE}")
    return [dict(r) for r in rows]


async def upsert_memory(records: list[dict]):
    if not records:
        return
    pool = await get_pool()
    if pool is None:
        for r in records:
            key = f"{r['table_catalog']}.{r['table_schema']}.{r['table_name']}.{r['column_name']}"
            _mem_memory[key] = {**r, "last_seen_at": datetime.now(timezone.utc).isoformat()}
        return
    async with pool.acquire() as conn:
        await conn.executemany(
            f"""
            INSERT INTO {MEMORY_TABLE}
                (table_catalog, table_schema, table_name, column_name,
                 data_type, column_comment, fingerprint, last_seen_at)
            VALUES ($1, $2, $3, $4, $5, $6, $7, NOW())
            ON CONFLICT (table_catalog, table_schema, table_name, column_name)
            DO UPDATE SET
                data_type = EXCLUDED.data_type,
                column_comment = EXCLUDED.column_comment,
                fingerprint = EXCLUDED.fingerprint,
                last_seen_at = NOW()
            """,
            [
                (
                    r["table_catalog"], r["table_schema"], r["table_name"],
                    r["column_name"], r.get("data_type"), r.get("column_comment"),
                    r["fingerprint"],
                )
                for r in records
            ],
        )


async def delete_memory(records: list[dict]):
    if not records:
        return
    pool = await get_pool()
    if pool is None:
        for r in records:
            key = f"{r['table_catalog']}.{r['table_schema']}.{r['table_name']}.{r['column_name']}"
            _mem_memory.pop(key, None)
        return
    async with pool.acquire() as conn:
        for r in records:
            await conn.execute(
                f"""DELETE FROM {MEMORY_TABLE}
                    WHERE table_catalog=$1 AND table_schema=$2
                      AND table_name=$3 AND column_name=$4""",
                r["table_catalog"], r["table_schema"],
                r["table_name"], r["column_name"],
            )


# ---------------------------------------------------------------------------
# Trail helpers
# ---------------------------------------------------------------------------

async def insert_trail(run: dict):
    pool = await get_pool()
    if pool is None:
        _mem_trails.insert(0, {
            "run_id": run["run_id"],
            "started_at": (run.get("started_at") or datetime.now(timezone.utc)).isoformat(),
            "finished_at": None,
            "catalogs": run["catalogs"],
            "mode": run["mode"],
            "changes_detected": None,
            "suggestions": None,
            "applied": None,
            "notification_status": run.get("notification_status", "deferred"),
        })
        return
    async with pool.acquire() as conn:
        await conn.execute(
            f"""
            INSERT INTO {TRAIL_TABLE}
                (run_id, started_at, catalogs, mode, notification_status)
            VALUES ($1, $2, $3, $4, $5)
            """,
            run["run_id"],
            run.get("started_at", datetime.now(timezone.utc)),
            run["catalogs"],
            run["mode"],
            run.get("notification_status", "deferred"),
        )


async def update_trail(run_id: str, **fields):
    pool = await get_pool()
    if pool is None:
        for entry in _mem_trails:
            if entry["run_id"] == run_id:
                for k, v in fields.items():
                    if isinstance(v, datetime):
                        v = v.isoformat()
                    entry[k] = v
                break
        return
    sets = []
    vals = []
    idx = 1
    for k, v in fields.items():
        if isinstance(v, (dict, list)):
            v = json.dumps(v)
        sets.append(f"{k} = ${idx}")
        vals.append(v)
        idx += 1
    vals.append(run_id)
    async with pool.acquire() as conn:
        await conn.execute(
            f"UPDATE {TRAIL_TABLE} SET {', '.join(sets)} WHERE run_id = ${idx}",
            *vals,
        )


async def get_trails(limit: int = 50) -> list[dict]:
    pool = await get_pool()
    if pool is None:
        return _mem_trails[:limit]
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            f"SELECT * FROM {TRAIL_TABLE} ORDER BY started_at DESC LIMIT $1", limit
        )
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Classification helpers
# ---------------------------------------------------------------------------

async def insert_classifications(records: list[dict]):
    if not records:
        return
    pool = await get_pool()
    if pool is None:
        _mem_classifications.extend(records)
        return
    async with pool.acquire() as conn:
        await conn.executemany(
            f"""
            INSERT INTO {CLASSIFICATION_TABLE}
                (run_id, table_catalog, table_schema, table_name, column_name,
                 predicted_labels, confidence, model_name, model_version)
            VALUES ($1, $2, $3, $4, $5, $6::jsonb, $7, $8, $9)
            """,
            [
                (
                    r["run_id"], r["table_catalog"], r["table_schema"],
                    r["table_name"], r["column_name"],
                    json.dumps(r["predicted_labels"]),
                    r.get("confidence"),
                    r.get("model_name"),
                    r.get("model_version"),
                )
                for r in records
            ],
        )


async def get_classifications(run_id: str) -> list[dict]:
    pool = await get_pool()
    if pool is None:
        return [r for r in _mem_classifications if r.get("run_id") == run_id]
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            f"SELECT * FROM {CLASSIFICATION_TABLE} WHERE run_id = $1 ORDER BY id", run_id
        )
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Notification candidate helpers
# ---------------------------------------------------------------------------

async def insert_notification_candidates(records: list[dict]):
    if not records:
        return
    pool = await get_pool()
    if pool is None:
        _mem_notifications.extend(records)
        return
    async with pool.acquire() as conn:
        await conn.executemany(
            f"""
            INSERT INTO {NOTIFICATION_TABLE}
                (run_id, column_fqn, labels, status)
            VALUES ($1, $2, $3::jsonb, $4)
            """,
            [
                (
                    r["run_id"], r["column_fqn"],
                    json.dumps(r["labels"]), r.get("status", "pending"),
                )
                for r in records
            ],
        )
