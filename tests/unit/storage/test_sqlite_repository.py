"""Unit tests for SQLite repository, schema migrations, and retention controls."""

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from workbench.adapters.storage.sqlite_repository import JobRunRecord, SqliteRepository
from workbench.domain.errors import StorageFailureError, ValidationError
from workbench.domain.operations import Operation
from workbench.domain.pipeline import Pipeline


@pytest.fixture
def repo(tmp_path: Path) -> SqliteRepository:
    db_file = tmp_path / "test_workbench.db"
    return SqliteRepository(db_path=db_file)


def test_schema_migrations_applied(repo: SqliteRepository) -> None:
    conn = repo._get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT version, name FROM schema_migrations ORDER BY version")
    rows = cursor.fetchall()
    assert len(rows) >= 1
    assert rows[0]["name"] == "initial_schema"
    conn.close()


def test_pipeline_crud(repo: SqliteRepository) -> None:
    # 1. Create and save pipeline
    op = Operation(
        name="trim_whitespace",
        columns=["name", "city"],
        parameters={},
    )
    pipeline = Pipeline(
        id="test-pipe-1",
        name="Customer Cleaner",
        version="1.0",
        steps=[op],
    )
    repo.save_pipeline(pipeline, description="Trims whitespace from names and cities")

    # 2. Retrieve pipeline
    fetched = repo.get_pipeline("test-pipe-1")
    assert fetched is not None
    assert fetched.name == "Customer Cleaner"
    assert len(fetched.steps) == 1
    assert fetched.steps[0].name == "trim_whitespace"

    # 3. List pipelines
    listed = repo.list_pipelines()
    assert len(listed) == 1
    assert listed[0]["id"] == "test-pipe-1"
    assert listed[0]["description"] == "Trims whitespace from names and cities"

    # 4. Update pipeline
    op2 = Operation(name="drop_duplicates", columns=[], parameters={})
    updated_pipe = pipeline.add_step(op2)
    repo.save_pipeline(updated_pipe, description="Updated cleaner")
    fetched_updated = repo.get_pipeline("test-pipe-1")
    assert fetched_updated is not None
    assert len(fetched_updated.steps) == 2

    # 5. Delete pipeline
    deleted = repo.delete_pipeline("test-pipe-1")
    assert deleted is True
    assert repo.get_pipeline("test-pipe-1") is None
    assert repo.delete_pipeline("test-pipe-1") is False


def test_job_run_telemetry_and_history(repo: SqliteRepository) -> None:
    now = datetime.now(UTC).isoformat()
    run = JobRunRecord(
        id="run-001",
        pipeline_id=None,
        pipeline_name="Cleaning Pipeline",
        input_filename="customers.csv",
        rows_before=1000,
        rows_after=980,
        rows_affected=50,
        execution_time_ms=124.5,
        status="success",
        executed_at=now,
    )
    repo.record_job_run(run)

    runs = repo.list_job_runs()
    assert len(runs) == 1
    assert runs[0].id == "run-001"
    assert runs[0].rows_affected == 50
    assert runs[0].rows_before == 1000

    fetched = repo.get_job_run("run-001")
    assert fetched is not None
    assert fetched.input_filename == "customers.csv"


def test_retention_and_purge_controls(repo: SqliteRepository) -> None:
    # Create an old run (30 days ago) and a recent run
    old_time = (datetime.now(UTC) - timedelta(days=30)).isoformat()
    recent_time = datetime.now(UTC).isoformat()

    old_run = JobRunRecord(
        id="old-run",
        pipeline_id=None,
        pipeline_name="Legacy Run",
        input_filename="old.csv",
        rows_before=50,
        rows_after=50,
        rows_affected=0,
        execution_time_ms=10.0,
        status="success",
        executed_at=old_time,
    )
    recent_run = JobRunRecord(
        id="recent-run",
        pipeline_id=None,
        pipeline_name="Recent Run",
        input_filename="new.csv",
        rows_before=50,
        rows_after=50,
        rows_affected=0,
        execution_time_ms=12.0,
        status="success",
        executed_at=recent_time,
    )

    repo.record_job_run(old_run)
    repo.record_job_run(recent_run)
    assert len(repo.list_job_runs()) == 2

    # Purge runs older than 7 days
    deleted = repo.purge_job_runs(older_than_days=7)
    assert deleted == 1

    remaining = repo.list_job_runs()
    assert len(remaining) == 1
    assert remaining[0].id == "recent-run"

    # Purge all remaining
    deleted_all = repo.purge_job_runs(older_than_days=None)
    assert deleted_all == 1
    assert len(repo.list_job_runs()) == 0


def test_settings_storage(repo: SqliteRepository) -> None:
    repo.set_setting("theme", "dark")
    repo.set_setting("auto_preview", True)

    assert repo.get_setting("theme") == "dark"
    assert repo.get_setting("auto_preview") is True
    assert repo.get_setting("non_existent", default="fallback") == "fallback"

    settings = repo.list_settings()
    assert settings["theme"] == "dark"
    assert settings["auto_preview"] is True

    repo.delete_setting("theme")
    assert repo.get_setting("theme") is None


def test_invalid_purge_parameter(repo: SqliteRepository) -> None:
    with pytest.raises(ValidationError):
        repo.purge_job_runs(older_than_days=-5)


def test_database_corruption_handling(tmp_path: Path) -> None:
    corrupt_file = tmp_path / "corrupt.db"
    # Write garbage into the file header so SQLite cannot open it as a valid DB
    corrupt_file.write_bytes(b"THIS IS NOT A VALID SQLITE3 DATABASE FILE AT ALL 1234567890")

    with pytest.raises(StorageFailureError, match="file is not a database"):
        SqliteRepository(db_path=corrupt_file)
