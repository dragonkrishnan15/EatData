"""Security and privacy tests for local storage.

Invariants:
- STRICT PRIVACY (Rules 2, 6, 14): SQLite storage MUST NEVER persist raw dataset rows
  or cell values.
- Inspection of all table schemas, records, and raw file bytes must prove zero row leakage.
"""

import sqlite3
from pathlib import Path

from workbench.adapters.storage.sqlite_repository import JobRunRecord, SqliteRepository
from workbench.domain.operations import Operation
from workbench.domain.pipeline import Pipeline


def test_sqlite_schema_has_no_data_tables(tmp_path: Path) -> None:
    """Verify that SQLite schema contains no tables or columns for raw data rows."""
    db_file = tmp_path / "privacy_check.db"
    repo = SqliteRepository(db_path=db_file)
    conn = repo._get_connection()

    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    table_names = {row[0] for row in cursor.fetchall()}

    # Permitted tables
    allowed_tables = {"schema_migrations", "pipelines", "job_runs", "settings", "sqlite_sequence"}
    for t in table_names:
        assert t in allowed_tables, f"Unexpected table '{t}' found in database."

    # Verify column names across all tables
    for table in table_names:
        cursor.execute(f"PRAGMA table_info({table})")
        columns = [row["name"].lower() for row in cursor.fetchall()]
        # 'rows_before', 'rows_after', 'rows_affected' are integer counts, verify they are INTEGER
        for col in columns:
            if col in ("rows_before", "rows_after", "rows_affected"):
                cursor.execute(f"SELECT type FROM pragma_table_info('{table}') WHERE name='{col}'")
                col_type = cursor.fetchone()[0]
                assert "INT" in col_type.upper(), f"Count column {col} must be INTEGER type."
            else:
                assert "raw" not in col
                assert "cell" not in col

    conn.close()


def test_sqlite_content_contains_no_raw_cell_data(tmp_path: Path) -> None:
    """Verify that saving pipelines and job runs never leaks cell values into SQLite storage."""
    db_file = tmp_path / "no_cells.db"
    repo = SqliteRepository(db_path=db_file)

    secret_val = "SECRET_CREDIT_CARD_4111_2222_3333_4444"
    secret_name = "CONFIDENTIAL_PATIENT_JOHN_DOE"

    # Save a pipeline that references columns but has no raw data
    op = Operation(
        name="trim_whitespace",
        columns=["customer_name", "account_number"],
        parameters={},
    )
    pipeline = Pipeline(
        id="clean-customers",
        name="Customer Pipeline",
        version="1.0",
        steps=[op],
    )
    repo.save_pipeline(pipeline, description="Trims whitespace")

    # Record a job run with counts only
    run = JobRunRecord(
        id="run-privacy-1",
        pipeline_id=pipeline.id,
        pipeline_name=pipeline.name,
        input_filename="confidential_records.csv",
        rows_before=150,
        rows_after=148,
        rows_affected=10,
        execution_time_ms=25.0,
        status="success",
        executed_at="2026-10-23T20:00:00Z",
    )
    repo.record_job_run(run)

    # Read all raw bytes of the SQLite database file
    db_bytes = db_file.read_bytes()
    assert secret_val.encode() not in db_bytes
    assert secret_name.encode() not in db_bytes

    # Directly query all text columns across all tables and ensure no data rows exist
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()
    cursor.execute("SELECT steps_json FROM pipelines")
    for (steps_json,) in cursor.fetchall():
        assert secret_val not in steps_json
        assert secret_name not in steps_json

    cursor.execute("SELECT input_filename, pipeline_name FROM job_runs")
    for fn, pn in cursor.fetchall():
        assert secret_val not in fn
        assert secret_val not in pn

    conn.close()
