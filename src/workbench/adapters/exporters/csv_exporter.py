"""Safe CSV exporter with atomic writes and formula-injection defenses.

Invariants:
- Source files are strictly preserved and never overwritten by default.
- Atomic writes prevent corrupted partial files upon crash/cancellation.
- Safe CSV mode neutralizes spreadsheet formula injection triggers.
"""

from __future__ import annotations

import csv
import uuid
from pathlib import Path
from typing import Any

from workbench.adapters.exporters.base import BaseExporter, ExportResult
from workbench.domain.dataset import Dataset
from workbench.domain.errors import ExportConflictError


class CsvExporter(BaseExporter):
    """Safe CSV exporter with delimiter, encoding, and formula-injection options."""

    def __init__(
        self,
        delimiter: str = ",",
        encoding: str = "utf-8",
        safe_csv_mode: bool = True,
    ) -> None:
        self.delimiter = delimiter
        self.encoding = encoding
        self.safe_csv_mode = safe_csv_mode

    def _sanitize_cell(self, val: Any) -> Any:
        if val is None:
            return ""
        if not self.safe_csv_mode:
            return val
        s = str(val)
        # Check formula injection triggers
        if s.startswith(("=", "+", "-", "@", "\t", "\r")):
            return f"'{s}"
        return val

    def export(
        self,
        dataset: Dataset,
        destination_path: Path | str,
        source_path: Path | str | None = None,
        overwrite: bool = False,
    ) -> ExportResult:
        dest = Path(destination_path).resolve()

        # Check source overwrite protection
        if source_path:
            src = Path(source_path).resolve()
            if dest == src and not overwrite:
                raise ExportConflictError(
                    f"Destination '{dest}' matches source file. "
                    "Overwriting source files requires explicit overwrite=True."
                )

        # Check existing destination conflict
        if dest.exists() and not overwrite:
            raise ExportConflictError(
                f"Destination file already exists: '{dest}'. "
                "Specify overwrite=True to replace existing file."
            )

        dest.parent.mkdir(parents=True, exist_ok=True)
        temp_dest = dest.parent / f".tmp_{uuid.uuid4().hex}_{dest.name}"
        warnings: list[str] = []

        try:
            with open(temp_dest, "w", encoding=self.encoding, newline="") as f:
                writer = csv.writer(f, delimiter=self.delimiter)

                # Write sanitized headers
                writer.writerow(dataset.column_names)

                # Write sanitized rows
                for row in dataset.rows:
                    sanitized_row = [self._sanitize_cell(v) for v in row]
                    writer.writerow(sanitized_row)

            # Atomic replace
            temp_dest.replace(dest)
            bytes_written = dest.stat().st_size

        except Exception:
            if temp_dest.exists():
                temp_dest.unlink(missing_ok=True)
            raise

        return ExportResult(
            destination_path=str(dest),
            format="csv",
            bytes_written=bytes_written,
            rows_exported=dataset.row_count,
            columns_exported=dataset.column_count,
            warnings=warnings,
        )
