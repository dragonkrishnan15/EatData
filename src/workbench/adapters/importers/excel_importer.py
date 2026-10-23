"""Safe, zero-dependency Excel (.xlsx) importer.

Invariants:
- Uses standard library zipfile and xml.etree.ElementTree (no external binary dependencies).
- Strictly read-only handling of source files.
- Enforces configurable resource limits (file size, rows, columns).
- Emits structured domain errors on corruption or limits violation.
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path
from typing import Any
from uuid import uuid4

from workbench.adapters.importers.base import BaseImporter, ImportLimits, ImportResult
from workbench.domain.dataset import ColumnMetadata, Dataset, DataType
from workbench.domain.errors import ParseFailureError, ResourceLimitError

NS = {
    "s": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    "pkg_r": "http://schemas.openxmlformats.org/package/2006/relationships",
}


def _col_letter_to_index(col_str: str) -> int:
    """Convert Excel column letters (A, B, Z, AA) to zero-based integer index."""
    idx = 0
    for char in col_str:
        idx = idx * 26 + (ord(char) - ord("A") + 1)
    return idx - 1


class ExcelImporter(BaseImporter):
    """Safe reader for Excel (.xlsx) workbooks without external dependencies."""

    def __init__(self, limits: ImportLimits | None = None) -> None:
        self.default_limits = limits or ImportLimits()

    def import_file(
        self,
        path: Path | str,
        limits: ImportLimits | None = None,
        sheet_name: str | None = None,
        sheet_index: int = 0,
    ) -> ImportResult:
        file_path = Path(path)
        actual_limits = limits or self.default_limits

        if not file_path.exists():
            raise ParseFailureError(f"Excel file not found: '{file_path}'")
        if not file_path.is_file():
            raise ParseFailureError(f"Source path is not a regular file: '{file_path}'")

        file_size = file_path.stat().st_size
        if file_size > actual_limits.max_file_size_bytes:
            raise ResourceLimitError(
                f"File size {file_size} exceeds maximum allowed "
                f"{actual_limits.max_file_size_bytes} bytes."
            )

        if not zipfile.is_zipfile(file_path):
            raise ParseFailureError(
                f"Failed to read Excel file: '{file_path.name}' is not a valid archive."
            )

        try:
            with zipfile.ZipFile(file_path, "r") as z:
                # 1. Parse Shared Strings
                shared_strings: list[str] = []
                if "xl/sharedStrings.xml" in z.namelist():
                    with z.open("xl/sharedStrings.xml") as s_file:
                        tree = ET.parse(s_file)
                        root = tree.getroot()
                        for si in root.findall(".//s:si", NS):
                            texts = [t.text or "" for t in si.findall(".//s:t", NS)]
                            shared_strings.append("".join(texts))

                # 2. Determine target worksheet
                target_sheet = self._resolve_sheet_path(z, sheet_name, sheet_index)

                # 3. Parse Worksheet Rows
                with z.open(target_sheet) as sheet_file:
                    tree = ET.parse(sheet_file)
                    root = tree.getroot()

                raw_rows: list[list[Any]] = []
                sheet_data = root.find("s:sheetData", NS)
                if sheet_data is None:
                    empty_ds = Dataset(
                        id=str(uuid4()),
                        name=file_path.stem,
                        columns=[],
                        rows=[],
                    )
                    return ImportResult(
                        dataset=empty_ds,
                        source_path=str(file_path),
                        file_size_bytes=file_size,
                        detected_encoding="utf-8",
                    )

                for row_elem in sheet_data.findall("s:row", NS):
                    row_cells: dict[int, Any] = {}
                    for c_elem in row_elem.findall("s:c", NS):
                        ref = c_elem.get("r", "")
                        match = re.match(r"^([A-Z]+)", ref)
                        col_idx = _col_letter_to_index(match.group(1)) if match else len(row_cells)

                        cell_type = c_elem.get("t", "")
                        val_elem = c_elem.find("s:v", NS)
                        raw_val = val_elem.text if val_elem is not None and val_elem.text else ""

                        parsed_val: Any = raw_val
                        if cell_type == "s" and raw_val.isdigit():
                            s_idx = int(raw_val)
                            parsed_val = (
                                shared_strings[s_idx] if s_idx < len(shared_strings) else ""
                            )
                        elif cell_type == "inlineStr":
                            is_elem = c_elem.find("s:is", NS)
                            if is_elem is not None:
                                t_elems = is_elem.findall(".//s:t", NS)
                                parsed_val = "".join([t.text or "" for t in t_elems])
                        elif cell_type == "b":
                            parsed_val = "true" if raw_val == "1" else "false"
                        elif not cell_type and raw_val:
                            # Attempt int / float conversion for numbers
                            try:
                                parsed_val = int(raw_val)
                            except ValueError:
                                try:
                                    parsed_val = float(raw_val)
                                except ValueError:
                                    parsed_val = raw_val

                        row_cells[col_idx] = parsed_val

                    if row_cells:
                        max_idx = max(row_cells.keys())
                        row_list = [row_cells.get(i, None) for i in range(max_idx + 1)]
                        raw_rows.append(row_list)
                        if len(raw_rows) - 1 > actual_limits.max_rows:
                            raise ResourceLimitError(
                                f"Excel row count exceeds maximum allowed {actual_limits.max_rows}."
                            )

        except (ResourceLimitError, ParseFailureError):
            raise
        except zipfile.BadZipFile as err:
            raise ParseFailureError(f"Failed to read Excel file: Corrupt archive: {err}") from err
        except ET.ParseError as err:
            raise ParseFailureError(f"Failed to read Excel file: Malformed XML: {err}") from err
        except Exception as err:
            raise ParseFailureError(f"Failed to read Excel file: {err}") from err

        if not raw_rows:
            empty_ds = Dataset(id=str(uuid4()), name=file_path.stem, columns=[], rows=[])
            return ImportResult(
                dataset=empty_ds,
                source_path=str(file_path),
                file_size_bytes=file_size,
                detected_encoding="utf-8",
            )

        # Header row
        header_vals = raw_rows[0]
        if len(header_vals) > actual_limits.max_columns:
            raise ResourceLimitError(
                f"Column count {len(header_vals)} exceeds maximum allowed "
                f"{actual_limits.max_columns}."
            )

        col_names: list[str] = []
        for i, h in enumerate(header_vals):
            clean_name = str(h).strip() if h is not None else f"col_{i + 1}"
            col_names.append(clean_name or f"col_{i + 1}")

        # Normalize data rows to column count
        col_count = len(col_names)
        data_rows: list[tuple[Any, ...]] = []
        for r in raw_rows[1:]:
            padded = r[:col_count] + [None] * max(0, col_count - len(r))
            data_rows.append(tuple(padded))

        columns = [
            ColumnMetadata(name=name, data_type=DataType.STRING, is_nullable=True)
            for name in col_names
        ]

        dataset = Dataset(
            id=str(uuid4()),
            name=file_path.stem,
            columns=columns,
            rows=data_rows,
        )

        return ImportResult(
            dataset=dataset,
            source_path=str(file_path),
            file_size_bytes=file_size,
            detected_encoding="utf-8",
        )

    def _resolve_sheet_path(
        self,
        z: zipfile.ZipFile,
        sheet_name: str | None,
        sheet_index: int,
    ) -> str:
        """Resolve the zip archive part name for the selected sheet."""
        # Map sheet name to relationship ID via xl/workbook.xml
        sheet_rel_map: dict[str, str] = {}
        if "xl/workbook.xml" in z.namelist():
            with z.open("xl/workbook.xml") as wb_file:
                wb_tree = ET.parse(wb_file)
                for s in wb_tree.getroot().findall(".//s:sheet", NS):
                    s_name = s.get("name")
                    r_id = s.get(
                        "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"
                    ) or s.get("r:id")
                    if s_name and r_id:
                        sheet_rel_map[s_name] = r_id

        # Map relationship ID to sheet part name via xl/_rels/workbook.xml.rels
        rel_target_map: dict[str, str] = {}
        rels_path = "xl/_rels/workbook.xml.rels"
        if rels_path in z.namelist():
            with z.open(rels_path) as rels_file:
                rels_tree = ET.parse(rels_file)
                for r in rels_tree.getroot():
                    r_id = r.get("Id")
                    target = r.get("Target")
                    if r_id and target:
                        # Normalize relative path: Target is e.g. "worksheets/sheet1.xml"
                        if not target.startswith("xl/"):
                            target = f"xl/{target}"
                        rel_target_map[r_id] = target

        if sheet_name is not None:
            if sheet_name not in sheet_rel_map:
                raise ParseFailureError(
                    f"Sheet '{sheet_name}' not found in Excel workbook. "
                    f"Available sheets: {list(sheet_rel_map.keys())}"
                )
            r_id = sheet_rel_map[sheet_name]
            if r_id in rel_target_map and rel_target_map[r_id] in z.namelist():
                return rel_target_map[r_id]

        # Fallback to sheet_index or alphabetical sheet file list
        sheet_files = [n for n in z.namelist() if re.match(r"^xl/worksheets/sheet\d+\.xml$", n)]
        sheet_files.sort()
        if not sheet_files:
            raise ParseFailureError("No worksheet found inside Excel archive.")

        idx = max(0, min(sheet_index, len(sheet_files) - 1))
        return sheet_files[idx]
