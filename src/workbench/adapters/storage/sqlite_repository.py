"""SQLite persistence repository for pipelines, run history, and settings.

Invariants:
- STRICT PRIVACY: NEVER persist raw dataset rows, individual cell values, or credentials.
- Schema versioning and transactional migrations are enforced at connection initialization.
- Gracefully handles database corruption or permission errors via StorageFailureError.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from workbench.adapters.storage.schema import apply_migrations
from workbench.domain.errors import StorageFailureError, ValidationError
from workbench.domain.pipeline import Pipeline


@dataclass(frozen=True)
class JobRunRecord:
    """Telemetry record of a pipeline transformation execution."""

    id: str
    pipeline_id: str | None
    pipeline_name: str
    input_filename: str
    rows_before: int
    rows_after: int
    rows_affected: int
    execution_time_ms: float
    status: str  # "success", "failed", "cancelled"
    executed_at: str
    error_message: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> JobRunRecord:
        return cls(
            id=row["id"],
            pipeline_id=row["pipeline_id"],
            pipeline_name=row["pipeline_name"],
            input_filename=row["input_filename"],
            rows_before=row["rows_before"],
            rows_after=row["rows_after"],
            rows_affected=row["rows_affected"],
            execution_time_ms=row["execution_time_ms"],
            status=row["status"],
            error_message=row["error_message"],
            executed_at=row["executed_at"],
        )


def get_default_repository() -> SqliteRepository:
    """Return default repository located at ~/.eatdata/workbench.db."""
    db_path = Path.home() / ".eatdata" / "workbench.db"
    return SqliteRepository(db_path=db_path)


class SqliteRepository:
    """Thread-safe SQLite storage for workbench state and execution history."""

    def __init__(self, db_path: Path | str = ":memory:") -> None:
        self.db_path = str(db_path)
        if self.db_path != ":memory:":
            p = Path(self.db_path)
            p.parent.mkdir(parents=True, exist_ok=True)

        try:
            self._init_db()
        except sqlite3.DatabaseError as err:
            raise StorageFailureError(
                f"Failed to initialize SQLite database at '{self.db_path}': {err}"
            ) from err

    def _get_connection(self) -> sqlite3.Connection:
        """Create and configure a fresh SQLite connection."""
        try:
            conn = sqlite3.connect(self.db_path, timeout=10.0)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA foreign_keys = ON;")
            conn.execute("PRAGMA journal_mode = WAL;")
            return conn
        except sqlite3.DatabaseError as err:
            raise StorageFailureError(
                f"Database connection error for '{self.db_path}': {err}"
            ) from err

    def _init_db(self) -> None:
        """Apply schema migrations to ensure schema is up-to-date."""
        conn = self._get_connection()
        try:
            apply_migrations(conn)
        finally:
            conn.close()

    # --- Pipeline Persistence ---

    def save_pipeline(self, pipeline: Pipeline, description: str = "") -> None:
        """Insert or update a pipeline definition."""
        now = datetime.now(UTC).isoformat()
        steps_json = json.dumps([s.to_dict() for s in pipeline.steps])

        conn = self._get_connection()
        try:
            with conn:
                conn.execute(
                    """
                    INSERT INTO pipelines (
                        id, name, version, description, steps_json, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(id) DO UPDATE SET
                        name = excluded.name,
                        version = excluded.version,
                        description = excluded.description,
                        steps_json = excluded.steps_json,
                        updated_at = excluded.updated_at
                    """,
                    (
                        pipeline.id,
                        pipeline.name,
                        pipeline.version,
                        description,
                        steps_json,
                        now,
                        now,
                    ),
                )
        except sqlite3.DatabaseError as err:
            raise StorageFailureError(f"Failed to save pipeline '{pipeline.id}': {err}") from err
        finally:
            conn.close()

    def get_pipeline(self, pipeline_id: str) -> Pipeline | None:
        """Retrieve a pipeline definition by ID."""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM pipelines WHERE id = ?", (pipeline_id,))
            row = cursor.fetchone()
            if not row:
                return None

            steps_data = json.loads(row["steps_json"])
            return Pipeline.from_dict(
                {
                    "id": row["id"],
                    "name": row["name"],
                    "version": row["version"],
                    "steps": steps_data,
                }
            )
        except sqlite3.DatabaseError as err:
            raise StorageFailureError(f"Failed to get pipeline '{pipeline_id}': {err}") from err
        finally:
            conn.close()

    def list_pipelines(self) -> list[dict[str, Any]]:
        """List all saved pipeline metadata."""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id, name, version, description, created_at, updated_at "
                "FROM pipelines ORDER BY updated_at DESC"
            )
            rows = cursor.fetchall()
            return [
                {
                    "id": r["id"],
                    "name": r["name"],
                    "version": r["version"],
                    "description": r["description"],
                    "created_at": r["created_at"],
                    "updated_at": r["updated_at"],
                }
                for r in rows
            ]
        except sqlite3.DatabaseError as err:
            raise StorageFailureError(f"Failed to list pipelines: {err}") from err
        finally:
            conn.close()

    def delete_pipeline(self, pipeline_id: str) -> bool:
        """Delete a saved pipeline definition."""
        conn = self._get_connection()
        try:
            with conn:
                cursor = conn.execute("DELETE FROM pipelines WHERE id = ?", (pipeline_id,))
                return cursor.rowcount > 0
        except sqlite3.DatabaseError as err:
            raise StorageFailureError(f"Failed to delete pipeline '{pipeline_id}': {err}") from err
        finally:
            conn.close()

    # --- Execution History ---

    def record_job_run(self, run: JobRunRecord) -> None:
        """Record execution metrics and summary for a pipeline job."""
        conn = self._get_connection()
        try:
            with conn:
                conn.execute(
                    """
                    INSERT INTO job_runs (
                        id, pipeline_id, pipeline_name, input_filename,
                        rows_before, rows_after, rows_affected,
                        execution_time_ms, status, error_message, executed_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        run.id,
                        run.pipeline_id,
                        run.pipeline_name,
                        run.input_filename,
                        run.rows_before,
                        run.rows_after,
                        run.rows_affected,
                        run.execution_time_ms,
                        run.status,
                        run.error_message,
                        run.executed_at,
                    ),
                )
        except sqlite3.DatabaseError as err:
            raise StorageFailureError(f"Failed to record job run '{run.id}': {err}") from err
        finally:
            conn.close()

    def list_job_runs(
        self, limit: int = 50, offset: int = 0, status: str | None = None
    ) -> list[JobRunRecord]:
        """List past pipeline execution runs."""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            if status:
                cursor.execute(
                    "SELECT * FROM job_runs WHERE status = ? "
                    "ORDER BY executed_at DESC LIMIT ? OFFSET ?",
                    (status, limit, offset),
                )
            else:
                cursor.execute(
                    "SELECT * FROM job_runs ORDER BY executed_at DESC LIMIT ? OFFSET ?",
                    (limit, offset),
                )
            rows = cursor.fetchall()
            return [JobRunRecord.from_row(r) for r in rows]
        except sqlite3.DatabaseError as err:
            raise StorageFailureError(f"Failed to list job runs: {err}") from err
        finally:
            conn.close()

    def get_job_run(self, run_id: str) -> JobRunRecord | None:
        """Fetch a single job run by ID."""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM job_runs WHERE id = ?", (run_id,))
            row = cursor.fetchone()
            return JobRunRecord.from_row(row) if row else None
        except sqlite3.DatabaseError as err:
            raise StorageFailureError(f"Failed to get job run '{run_id}': {err}") from err
        finally:
            conn.close()

    def purge_job_runs(self, older_than_days: int | None = None) -> int:
        """Retention control: delete execution runs.

        If older_than_days is provided, only deletes runs older than that threshold.
        If older_than_days is None, deletes all execution runs.
        Returns the number of deleted records.
        """
        conn = self._get_connection()
        try:
            with conn:
                if older_than_days is not None:
                    if older_than_days < 0:
                        raise ValidationError("older_than_days cannot be negative.")
                    cutoff = datetime.now(UTC) - timedelta(days=older_than_days)
                    cursor = conn.execute(
                        "DELETE FROM job_runs WHERE executed_at < ?", (cutoff.isoformat(),)
                    )
                else:
                    cursor = conn.execute("DELETE FROM job_runs")
                return cursor.rowcount
        except sqlite3.DatabaseError as err:
            raise StorageFailureError(f"Failed to purge job runs: {err}") from err
        finally:
            conn.close()

    # --- Application Settings ---

    def set_setting(self, key: str, value: Any) -> None:
        """Store an application setting as JSON."""
        now = datetime.now(UTC).isoformat()
        val_json = json.dumps(value)
        conn = self._get_connection()
        try:
            with conn:
                conn.execute(
                    """
                    INSERT INTO settings (key, value_json, updated_at)
                    VALUES (?, ?, ?)
                    ON CONFLICT(key) DO UPDATE SET
                        value_json = excluded.value_json,
                        updated_at = excluded.updated_at
                    """,
                    (key, val_json, now),
                )
        except sqlite3.DatabaseError as err:
            raise StorageFailureError(f"Failed to set setting '{key}': {err}") from err
        finally:
            conn.close()

    def get_setting(self, key: str, default: Any = None) -> Any:
        """Retrieve an application setting, returning default if absent."""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT value_json FROM settings WHERE key = ?", (key,))
            row = cursor.fetchone()
            if not row:
                return default
            return json.loads(row["value_json"])
        except sqlite3.DatabaseError as err:
            raise StorageFailureError(f"Failed to get setting '{key}': {err}") from err
        finally:
            conn.close()

    def delete_setting(self, key: str) -> bool:
        """Delete an application setting."""
        conn = self._get_connection()
        try:
            with conn:
                cursor = conn.execute("DELETE FROM settings WHERE key = ?", (key,))
                return cursor.rowcount > 0
        except sqlite3.DatabaseError as err:
            raise StorageFailureError(f"Failed to delete setting '{key}': {err}") from err
        finally:
            conn.close()

    def list_settings(self) -> dict[str, Any]:
        """Return all stored settings as a dictionary."""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT key, value_json FROM settings")
            rows = cursor.fetchall()
            return {r["key"]: json.loads(r["value_json"]) for r in rows}
        except sqlite3.DatabaseError as err:
            raise StorageFailureError(f"Failed to list settings: {err}") from err
        finally:
            conn.close()
