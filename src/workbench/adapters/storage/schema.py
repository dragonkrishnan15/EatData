"""SQLite schema migrations and definitions.

Invariants:
- STRICT PRIVACY: Storage schemas MUST NEVER store raw dataset rows,
  cell contents, or unredacted secrets.
- All migrations are transactional and tracked in the schema_migrations table.
- Upgrades are strictly ordered, idempotent, and reversible where feasible.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Callable
from datetime import UTC

MIGRATION_V1 = """
-- Schema migrations tracker
CREATE TABLE IF NOT EXISTS schema_migrations (
    version INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    applied_at TEXT NOT NULL
);

-- Versioned pipeline definitions (specifications only, no raw data)
CREATE TABLE IF NOT EXISTS pipelines (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    version TEXT NOT NULL,
    description TEXT DEFAULT '',
    steps_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

-- Transformation execution runs telemetry (counts and timings only, no raw row values)
CREATE TABLE IF NOT EXISTS job_runs (
    id TEXT PRIMARY KEY,
    pipeline_id TEXT,
    pipeline_name TEXT NOT NULL,
    input_filename TEXT NOT NULL,
    rows_before INTEGER NOT NULL,
    rows_after INTEGER NOT NULL,
    rows_affected INTEGER NOT NULL,
    execution_time_ms REAL NOT NULL,
    status TEXT NOT NULL,
    error_message TEXT,
    executed_at TEXT NOT NULL,
    FOREIGN KEY(pipeline_id) REFERENCES pipelines(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_job_runs_executed_at ON job_runs(executed_at);
CREATE INDEX IF NOT EXISTS idx_job_runs_status ON job_runs(status);

-- Local application settings and configuration
CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value_json TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
"""

MIGRATIONS: list[tuple[int, str, str | Callable[[sqlite3.Connection], None]]] = [
    (1, "initial_schema", MIGRATION_V1),
]


def apply_migrations(conn: sqlite3.Connection) -> int:
    """Apply any pending schema migrations in order within transactions.

    Returns the total count of newly applied migrations.
    """
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            version INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            applied_at TEXT NOT NULL
        )
        """
    )
    conn.commit()

    cursor = conn.cursor()
    cursor.execute("SELECT version FROM schema_migrations")
    applied_versions = {row[0] for row in cursor.fetchall()}

    applied_count = 0
    for version, name, script_or_fn in MIGRATIONS:
        if version not in applied_versions:
            with conn:
                if callable(script_or_fn):
                    script_or_fn(conn)
                else:
                    conn.executescript(script_or_fn)

                from datetime import datetime

                now_iso = datetime.now(UTC).isoformat()
                conn.execute(
                    "INSERT INTO schema_migrations (version, name, applied_at) VALUES (?, ?, ?)",
                    (version, name, now_iso),
                )
            applied_count += 1

    return applied_count
