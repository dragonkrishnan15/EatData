"""Base contracts and limits for dataset importers.

Invariants:
- Importers must treat source files as strictly read-only.
- Configurable limits must be checked before and during file ingestion.
- Structured errors (ResourceLimitError, ParseFailureError) must be used.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path

from workbench.domain.dataset import Dataset


@dataclass(frozen=True)
class ImportLimits:
    """Configurable resource thresholds to prevent memory exhaustion."""

    max_file_size_bytes: int = 100 * 1024 * 1024  # 100 MB default
    max_rows: int = 500_000  # 500k rows default
    max_columns: int = 1_000  # 1k columns default
    max_json_depth: int = 20  # For nested structures


@dataclass(frozen=True)
class ImportResult:
    """Standardized output of a dataset import operation."""

    dataset: Dataset
    source_path: str
    file_size_bytes: int
    detected_encoding: str
    detected_delimiter: str | None = None
    warnings: list[str] = field(default_factory=list)


class BaseImporter(ABC):
    """Abstract base class for all file format importers."""

    @abstractmethod
    def import_file(
        self,
        path: Path | str,
        limits: ImportLimits | None = None,
    ) -> ImportResult:
        """Parse a source file and return an ImportResult with an immutable Dataset."""
