"""Safe JSON exporter with atomic writes and layout options.

Invariants:
- Source files are strictly preserved and never overwritten by default.
- Atomic writes prevent corrupted partial files upon crash/cancellation.
- Supports both standard JSON array of objects and JSON Lines (NDJSON).
"""

from __future__ import annotations

import json
import uuid
from pathlib import Path

from workbench.adapters.exporters.base import BaseExporter, ExportResult
from workbench.domain.dataset import Dataset
from workbench.domain.errors import ExportConflictError, ValidationError


class JsonExporter(BaseExporter):
    """Safe JSON exporter with format and layout options."""

    def __init__(
        self,
        layout: str = "records",  # "records" or "ndjson"
        indent: int = 2,
        encoding: str = "utf-8",
    ) -> None:
        if layout not in ("records", "ndjson"):
            raise ValidationError("JSON layout must be 'records' or 'ndjson'.")
        self.layout = layout
        self.indent = indent
        self.encoding = encoding

    def export(
        self,
        dataset: Dataset,
        destination_path: Path | str,
        source_path: Path | str | None = None,
        overwrite: bool = False,
    ) -> ExportResult:
        dest = Path(destination_path).resolve()

        if source_path:
            src = Path(source_path).resolve()
            if dest == src and not overwrite:
                raise ExportConflictError(
                    f"Destination '{dest}' matches source file. "
                    "Overwriting source files requires explicit overwrite=True."
                )

        if dest.exists() and not overwrite:
            raise ExportConflictError(
                f"Destination file already exists: '{dest}'. "
                "Specify overwrite=True to replace existing file."
            )

        dest.parent.mkdir(parents=True, exist_ok=True)
        temp_dest = dest.parent / f".tmp_{uuid.uuid4().hex}_{dest.name}"
        col_names = dataset.column_names

        try:
            with open(temp_dest, "w", encoding=self.encoding) as f:
                if self.layout == "records":
                    records = []
                    for row in dataset.rows:
                        records.append({col_names[i]: row[i] for i in range(len(col_names))})
                    json.dump(records, f, indent=self.indent)
                elif self.layout == "ndjson":
                    for row in dataset.rows:
                        rec = {col_names[i]: row[i] for i in range(len(col_names))}
                        f.write(json.dumps(rec) + "\n")

            # Atomic replace
            temp_dest.replace(dest)
            bytes_written = dest.stat().st_size

        except Exception:
            if temp_dest.exists():
                temp_dest.unlink(missing_ok=True)
            raise

        return ExportResult(
            destination_path=str(dest),
            format=f"json-{self.layout}",
            bytes_written=bytes_written,
            rows_exported=dataset.row_count,
            columns_exported=dataset.column_count,
            warnings=[],
        )
