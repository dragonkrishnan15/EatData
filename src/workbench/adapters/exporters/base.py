"""Base exporter contracts and export results.

Invariants:
- Never overwrite the original source file by default.
- Fail safely using atomic writes to avoid corrupted partial files.
- Return structured summary reports for all exports.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path

from workbench.domain.dataset import Dataset


@dataclass(frozen=True)
class ExportResult:
    """Telemetry and outcome summary of an export operation."""

    destination_path: str
    format: str
    bytes_written: int
    rows_exported: int
    columns_exported: int
    warnings: list[str] = field(default_factory=list)


class BaseExporter(ABC):
    """Abstract base class for dataset exporters."""

    @abstractmethod
    def export(
        self,
        dataset: Dataset,
        destination_path: Path | str,
        source_path: Path | str | None = None,
        overwrite: bool = False,
    ) -> ExportResult:
        """Export dataset to destination path."""
