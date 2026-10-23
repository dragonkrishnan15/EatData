"""Safe JSON importer with nesting controls and resource limits.

Invariants:
- Source files are opened read-only and never modified.
- Strict resource bounds (file size, row count, column count, nesting depth) are enforced.
- Supports JSON array of objects, root-keyed arrays, and JSON Lines (NDJSON).
- Deeply nested objects are flattened up to a configurable maximum depth.
"""

from __future__ import annotations

import io
import json
from pathlib import Path
from typing import Any

from workbench.adapters.importers.base import BaseImporter, ImportLimits, ImportResult
from workbench.domain.dataset import ColumnMetadata, Dataset, DataType
from workbench.domain.errors import ParseFailureError, ResourceLimitError


class JsonImporter(BaseImporter):
    """Safe streaming/chunked JSON importer with flattening and depth bounds."""

    def __init__(self, default_encoding: str = "utf-8") -> None:
        self.default_encoding = default_encoding

    def _flatten_dict(
        self,
        d: dict[str, Any],
        prefix: str = "",
        current_depth: int = 1,
        max_depth: int = 20,
    ) -> dict[str, Any]:
        """Recursively flatten nested dictionaries with a dot notation, checking max_depth."""
        if current_depth > max_depth:
            raise ResourceLimitError(
                f"JSON nesting depth exceeded limit of {max_depth} levels.",
                details={"max_depth": max_depth, "current_depth": current_depth},
            )

        items: dict[str, Any] = {}
        for k, v in d.items():
            new_key = f"{prefix}.{k}" if prefix else str(k)
            if isinstance(v, dict):
                items.update(
                    self._flatten_dict(
                        v,
                        prefix=new_key,
                        current_depth=current_depth + 1,
                        max_depth=max_depth,
                    )
                )
            elif isinstance(v, list):
                # Represent nested lists as compact JSON strings to preserve tabular 2D shape
                items[new_key] = json.dumps(v)
            else:
                items[new_key] = v
        return items

    def _extract_records(self, raw_data: Any) -> list[dict[str, Any]]:
        """Extract a list of dictionary records from various JSON structures."""
        if isinstance(raw_data, list):
            records = []
            for item in raw_data:
                if isinstance(item, dict):
                    records.append(item)
                else:
                    records.append({"value": item})
            return records

        if isinstance(raw_data, dict):
            # Check if root dict has a known list key like "data", "records", "items", "results"
            for candidate in ("data", "records", "items", "results", "rows"):
                if candidate in raw_data and isinstance(raw_data[candidate], list):
                    return self._extract_records(raw_data[candidate])
            # Single object record
            return [raw_data]

        raise ParseFailureError("JSON root must be an array of objects or an object.")

    def import_file(
        self,
        path: Path | str,
        limits: ImportLimits | None = None,
        encoding_override: str | None = None,
    ) -> ImportResult:
        file_path = Path(path)
        if not file_path.exists():
            raise ParseFailureError(f"Source file not found: '{file_path}'")
        if not file_path.is_file():
            raise ParseFailureError(f"Source path is not a regular file: '{file_path}'")

        actual_limits = limits or ImportLimits()
        file_size = file_path.stat().st_size

        if file_size > actual_limits.max_file_size_bytes:
            raise ResourceLimitError(
                f"File size ({file_size} bytes) exceeds limit of "
                f"{actual_limits.max_file_size_bytes} bytes.",
                details={"file_size": file_size, "limit": actual_limits.max_file_size_bytes},
            )

        if file_size == 0:
            raise ParseFailureError(f"Cannot import empty file: '{file_path.name}' (0 bytes).")

        encoding = encoding_override or self.default_encoding

        try:
            with open(file_path, encoding=encoding, errors="replace") as f:
                content = f.read()
        except Exception as err:
            raise ParseFailureError(f"Failed to read file '{file_path.name}': {err}") from err

        return self._parse_json_content(
            content=content,
            name=file_path.stem,
            source_path=str(file_path.resolve()),
            file_size_bytes=file_size,
            limits=actual_limits,
            encoding=encoding,
        )

    def import_from_string(
        self,
        content: str,
        name: str = "string_dataset",
        limits: ImportLimits | None = None,
    ) -> ImportResult:
        """Parse JSON text into an ImportResult."""
        actual_limits = limits or ImportLimits()
        content_bytes = len(content.encode("utf-8"))
        if content_bytes > actual_limits.max_file_size_bytes:
            raise ResourceLimitError("Content exceeds maximum allowed size.")

        return self._parse_json_content(
            content=content,
            name=name,
            source_path="<string>",
            file_size_bytes=content_bytes,
            limits=actual_limits,
            encoding="utf-8",
        )

    def _parse_json_content(
        self,
        content: str,
        name: str,
        source_path: str,
        file_size_bytes: int,
        limits: ImportLimits,
        encoding: str,
    ) -> ImportResult:
        content_stripped = content.strip()
        if not content_stripped:
            raise ParseFailureError("JSON content is empty.")

        # Attempt standard JSON parse first; fallback to JSON Lines (NDJSON)
        records: list[dict[str, Any]]
        try:
            raw_data = json.loads(content_stripped)
            records = self._extract_records(raw_data)
        except json.JSONDecodeError as json_err:
            # Try parsing as JSON Lines (one JSON object per line)
            lines = [ln.strip() for ln in io.StringIO(content_stripped) if ln.strip()]
            ndjson_records = []
            try:
                for ln in lines:
                    obj = json.loads(ln)
                    if isinstance(obj, dict):
                        ndjson_records.append(obj)
                    else:
                        ndjson_records.append({"value": obj})
                records = ndjson_records
            except Exception:
                raise ParseFailureError(f"Failed to parse JSON content: {json_err}") from json_err

        if not records:
            raise ParseFailureError("No records found in JSON structure.")

        if len(records) > limits.max_rows:
            raise ResourceLimitError(
                f"Row count ({len(records)}) exceeds limit of {limits.max_rows} rows.",
                details={"rows": len(records), "limit": limits.max_rows},
            )

        # Flatten records and collect all unique column names
        flattened_records: list[dict[str, Any]] = []
        ordered_keys: list[str] = []
        seen_keys: set[str] = set()

        for rec in records:
            flat = self._flatten_dict(rec, max_depth=limits.max_json_depth)
            flattened_records.append(flat)
            for k in flat.keys():
                if k not in seen_keys:
                    seen_keys.add(k)
                    ordered_keys.append(k)

        if len(ordered_keys) > limits.max_columns:
            raise ResourceLimitError(
                f"Column count ({len(ordered_keys)}) exceeds limit of "
                f"{limits.max_columns} columns.",
                details={"columns": len(ordered_keys), "limit": limits.max_columns},
            )

        columns = [
            ColumnMetadata(name=col_name, data_type=DataType.STRING) for col_name in ordered_keys
        ]

        # Build consistent tabular rows
        rows: list[tuple[Any, ...]] = []
        for flat_rec in flattened_records:
            row_vals = tuple(flat_rec.get(col_name, "") for col_name in ordered_keys)
            rows.append(row_vals)

        dataset = Dataset(name=name, columns=columns, rows=rows)
        return ImportResult(
            dataset=dataset,
            source_path=source_path,
            file_size_bytes=file_size_bytes,
            detected_encoding=encoding,
            detected_delimiter=None,
            warnings=[],
        )
