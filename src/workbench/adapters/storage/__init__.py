"""Storage adapter package."""

from workbench.adapters.storage.sqlite_repository import JobRunRecord, SqliteRepository

__all__ = ["JobRunRecord", "SqliteRepository"]
