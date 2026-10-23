"""Safe CSV importer with encoding/delimiter detection and resource limits.

Invariants:
- Source files are opened read-only and never modified.
- Strict resource bounds (file size, row count, column count) are enforced.
- Malformed data produces structured errors or documented warnings, never unhandled crashes.
"""

from __future__ import annotations

import csv
import io
from pathlib import Path
from typing import Any

from workbench.adapters.importers.base import BaseImporter, ImportLimits, ImportResult
from workbench.domain.dataset import ColumnMetadata, Dataset, DataType
from workbench.domain.errors import ParseFailureError, ResourceLimitError


class CsvImporter(BaseImporter):
    """Safe streaming CSV importer."""

    def __init__(
        self,
        default_encoding: str = "utf-8",
        strict: bool = False,
    ) -> None:
        self.default_encoding = default_encoding
        self.strict = strict

    def detect_encoding(self, path: Path) -> str:
        """Detect encoding using BOM check and utf-8 validation."""
        with open(path, "rb") as f:
            raw_start = f.read(4096)

        if not raw_start:
            return self.default_encoding

        # Check BOM
        if raw_start.startswith(b"\xef\xbb\xbf"):
            return "utf-8-sig"
        if raw_start.startswith((b"\xff\xfe", b"\xfe\xff")):
            return "utf-16"

        try:
            raw_start.decode("utf-8")
            return "utf-8"
        except UnicodeDecodeError:
            return "cp1252"

    def detect_delimiter(self, path: Path, encoding: str) -> str:
        """Sniff delimiter from sample bytes, defaulting to comma."""
        try:
            with open(path, encoding=encoding, errors="replace") as f:
                sample = f.read(8192)
            if not sample:
                return ","
            sniffer = csv.Sniffer()
            dialect = sniffer.sniff(sample, delimiters=[",", "\t", ";", "|"])
            return dialect.delimiter
        except Exception:
            return ","

    def _sanitize_headers(
        self, raw_headers: list[str], max_columns: int
    ) -> tuple[list[ColumnMetadata], list[str]]:
        """Sanitize and deduplicate column names."""
        if len(raw_headers) > max_columns:
            raise ResourceLimitError(
                f"Column count ({len(raw_headers)}) exceeds limit of {max_columns} columns.",
                details={"columns": len(raw_headers), "limit": max_columns},
            )

        col_names: list[str] = []
        seen_names: dict[str, int] = {}
        warnings: list[str] = []

        for idx, h in enumerate(raw_headers):
            clean_name = h.strip()
            if not clean_name:
                clean_name = f"unnamed_{idx + 1}"
                warnings.append(f"Column at index {idx} had no header; renamed to '{clean_name}'.")

            if clean_name in seen_names:
                seen_names[clean_name] += 1
                deduped_name = f"{clean_name}_{seen_names[clean_name]}"
                warnings.append(
                    f"Duplicate column '{clean_name}' at index {idx}; renamed to '{deduped_name}'."
                )
                clean_name = deduped_name
            else:
                seen_names[clean_name] = 1

            col_names.append(clean_name)

        columns = [ColumnMetadata(name=name, data_type=DataType.STRING) for name in col_names]
        return columns, warnings

    def import_file(
        self,
        path: Path | str,
        limits: ImportLimits | None = None,
        delimiter_override: str | None = None,
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

        encoding = encoding_override or self.detect_encoding(file_path)
        delimiter = delimiter_override or self.detect_delimiter(file_path, encoding)

        warnings: list[str] = []

        try:
            with open(file_path, encoding=encoding, errors="replace", newline="") as f:
                reader = csv.reader(f, delimiter=delimiter)

                try:
                    raw_headers = next(reader)
                except StopIteration as err:
                    raise ParseFailureError(
                        f"No records found in CSV file: '{file_path.name}'."
                    ) from err

                columns, header_warnings = self._sanitize_headers(
                    raw_headers, actual_limits.max_columns
                )
                warnings.extend(header_warnings)
                expected_cols = len(columns)

                rows: list[tuple[Any, ...]] = []
                for row_idx, row in enumerate(reader):
                    if len(rows) >= actual_limits.max_rows:
                        raise ResourceLimitError(
                            f"Row count exceeded limit of {actual_limits.max_rows} rows.",
                            details={"max_rows": actual_limits.max_rows},
                        )

                    if len(row) != expected_cols:
                        if self.strict:
                            raise ParseFailureError(
                                f"Row {row_idx + 1} has {len(row)} values, "
                                f"expected {expected_cols}."
                            )
                        if len(row) < expected_cols:
                            warnings.append(
                                f"Row {row_idx + 1} had {len(row)} values; "
                                f"padded to {expected_cols}."
                            )
                            adjusted_row = list(row) + [""] * (expected_cols - len(row))
                        else:
                            warnings.append(
                                f"Row {row_idx + 1} had {len(row)} values; "
                                f"truncated to {expected_cols}."
                            )
                            adjusted_row = list(row)[:expected_cols]
                        rows.append(tuple(adjusted_row))
                    else:
                        rows.append(tuple(row))

        except (ResourceLimitError, ParseFailureError):
            raise
        except Exception as err:
            raise ParseFailureError(f"Failed to parse CSV file '{file_path.name}': {err}") from err

        dataset = Dataset(
            name=file_path.stem,
            columns=columns,
            rows=rows,
        )

        return ImportResult(
            dataset=dataset,
            source_path=str(file_path.resolve()),
            file_size_bytes=file_size,
            detected_encoding=encoding,
            detected_delimiter=delimiter,
            warnings=warnings,
        )

    def import_from_string(
        self,
        content: str,
        name: str = "string_dataset",
        delimiter: str = ",",
        limits: ImportLimits | None = None,
    ) -> ImportResult:
        """Parse a CSV formatted string into an ImportResult."""
        actual_limits = limits or ImportLimits()
        content_bytes = len(content.encode("utf-8"))
        if content_bytes > actual_limits.max_file_size_bytes:
            raise ResourceLimitError("Content exceeds maximum allowed size.")

        reader = csv.reader(io.StringIO(content), delimiter=delimiter)
        try:
            raw_headers = next(reader)
        except StopIteration as err:
            raise ParseFailureError("No data found in CSV content.") from err

        columns, warnings = self._sanitize_headers(raw_headers, actual_limits.max_columns)
        rows = [tuple(row) for row in reader]

        dataset = Dataset(name=name, columns=columns, rows=rows)
        return ImportResult(
            dataset=dataset,
            source_path="<string>",
            file_size_bytes=content_bytes,
            detected_encoding="utf-8",
            detected_delimiter=delimiter,
            warnings=warnings,
        )
