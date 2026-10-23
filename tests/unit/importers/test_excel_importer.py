"""Unit tests for ExcelImporter (.xlsx zero-dependency ingestion)."""

from __future__ import annotations

import io
import zipfile
from pathlib import Path

import pytest

from workbench.adapters.importers.base import ImportLimits
from workbench.adapters.importers.excel_importer import ExcelImporter
from workbench.domain.errors import ParseFailureError, ResourceLimitError


def create_minimal_xlsx(
    sheets: dict[str, list[list[str | int | float | None]]],
) -> bytes:
    """Create a minimal valid OpenXML .xlsx file in memory."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        # [Content_Types].xml
        content_types = (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">\n'
            '  <Default Extension="rels" '
            'ContentType="application/vnd.openxmlformats-package.relationships+xml"/>\n'
            '  <Default Extension="xml" ContentType="application/xml"/>\n'
            '  <Override PartName="/xl/workbook.xml" '
            'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>\n'
            '  <Override PartName="/xl/sharedStrings.xml" '
            'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sharedStrings+xml"/>\n'
        )
        for i in range(1, len(sheets) + 1):
            content_types += (
                f'  <Override PartName="/xl/worksheets/sheet{i}.xml" '
                'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>\n'
            )
        content_types += "</Types>"
        zf.writestr("[Content_Types].xml", content_types)

        # _rels/.rels
        doc_type = (
            "http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument"
        )
        rels = (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">\n'
            f'  <Relationship Id="rId1" Type="{doc_type}" Target="xl/workbook.xml"/>\n'
            "</Relationships>"
        )
        zf.writestr("_rels/.rels", rels)

        # Build shared strings table
        shared_strings: list[str] = []
        string_to_id: dict[str, int] = {}

        def get_string_id(text: str) -> int:
            if text not in string_to_id:
                string_to_id[text] = len(shared_strings)
                shared_strings.append(text)
            return string_to_id[text]

        # xl/workbook.xml
        wb_xml = (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
            '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
            'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">\n'
            "  <sheets>\n"
        )
        sst_type = (
            "http://schemas.openxmlformats.org/officeDocument/2006/relationships/sharedStrings"
        )
        wb_rels = (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">\n'
            f'  <Relationship Id="rIdShared" Type="{sst_type}" Target="sharedStrings.xml"/>\n'
        )

        ws_type = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet"
        sheet_index = 1
        for sheet_name, rows in sheets.items():
            r_id = f"rIdSheet{sheet_index}"
            wb_xml += f'    <sheet name="{sheet_name}" sheetId="{sheet_index}" r:id="{r_id}"/>\n'
            wb_rels += (
                f'  <Relationship Id="{r_id}" Type="{ws_type}" '
                f'Target="worksheets/sheet{sheet_index}.xml"/>\n'
            )

            # Build sheet XML
            sheet_xml = (
                '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
                '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">\n'
                "  <sheetData>\n"
            )
            for row_idx, row in enumerate(rows, start=1):
                sheet_xml += f'    <row r="{row_idx}">\n'
                for col_idx, cell_value in enumerate(row):
                    if cell_value is None:
                        continue
                    col_letter = chr(65 + col_idx) if col_idx < 26 else "A"
                    cell_ref = f"{col_letter}{row_idx}"
                    if isinstance(cell_value, (int, float)):
                        sheet_xml += f'      <c r="{cell_ref}"><v>{cell_value}</v></c>\n'
                    else:
                        s_id = get_string_id(str(cell_value))
                        sheet_xml += f'      <c r="{cell_ref}" t="s"><v>{s_id}</v></c>\n'
                sheet_xml += "    </row>\n"
            sheet_xml += "  </sheetData>\n</worksheet>"
            zf.writestr(f"xl/worksheets/sheet{sheet_index}.xml", sheet_xml)
            sheet_index += 1

        wb_xml += "  </sheets>\n</workbook>"
        wb_rels += "</Relationships>"
        zf.writestr("xl/workbook.xml", wb_xml)
        zf.writestr("xl/_rels/workbook.xml.rels", wb_rels)

        # xl/sharedStrings.xml
        sst_xml = (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
            f'<sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
            f'count="{len(shared_strings)}" uniqueCount="{len(shared_strings)}">\n'
        )
        for s in shared_strings:
            sst_xml += f"  <si><t>{s}</t></si>\n"
        sst_xml += "</sst>"
        zf.writestr("xl/sharedStrings.xml", sst_xml)

    return buf.getvalue()


def test_import_basic_xlsx(tmp_path: Path) -> None:
    data = {
        "Customers": [
            ["id", "name", "age", "active"],
            [1, "Alice", 30, "true"],
            [2, "Bob", 25, "false"],
            [3, "Charlie", 35, None],
        ]
    }
    xlsx_bytes = create_minimal_xlsx(data)
    file_path = tmp_path / "test_data.xlsx"
    file_path.write_bytes(xlsx_bytes)

    importer = ExcelImporter()
    result = importer.import_file(file_path)

    assert result.dataset.name == "test_data"
    assert result.dataset.column_names == ["id", "name", "age", "active"]
    assert result.dataset.row_count == 3
    assert result.dataset.rows[0][1] == "Alice"
    assert result.dataset.rows[0][2] == 30
    assert result.dataset.rows[2][3] is None


def test_import_sheet_selection(tmp_path: Path) -> None:
    data = {
        "Summary": [["Metric", "Value"], ["Total", 100]],
        "Details": [["sku", "qty", "price"], ["A1", 10, 4.99], ["B2", 5, 12.50]],
    }
    xlsx_bytes = create_minimal_xlsx(data)
    file_path = tmp_path / "multi_sheet.xlsx"
    file_path.write_bytes(xlsx_bytes)

    importer = ExcelImporter()
    # Import specific sheet "Details"
    result = importer.import_file(file_path, sheet_name="Details")
    assert result.dataset.column_names == ["sku", "qty", "price"]
    assert result.dataset.row_count == 2
    assert result.dataset.rows[0][0] == "A1"


def test_import_nonexistent_sheet(tmp_path: Path) -> None:
    data = {"Sheet1": [["col1"], ["val1"]]}
    file_path = tmp_path / "sheets.xlsx"
    file_path.write_bytes(create_minimal_xlsx(data))

    importer = ExcelImporter()
    with pytest.raises(ParseFailureError, match="Sheet 'NonExistent' not found"):
        importer.import_file(file_path, sheet_name="NonExistent")


def test_import_file_size_limit(tmp_path: Path) -> None:
    data = {"Sheet1": [["col1"], ["val1"]]}
    file_path = tmp_path / "large.xlsx"
    file_path.write_bytes(create_minimal_xlsx(data))

    limits = ImportLimits(max_file_size_bytes=10)
    importer = ExcelImporter(limits=limits)
    with pytest.raises(ResourceLimitError, match="exceeds maximum allowed"):
        importer.import_file(file_path)


def test_import_row_limit(tmp_path: Path) -> None:
    data = {"Sheet1": [["col1"], ["val1"], ["val2"], ["val3"]]}
    file_path = tmp_path / "rows.xlsx"
    file_path.write_bytes(create_minimal_xlsx(data))

    limits = ImportLimits(max_rows=2)
    importer = ExcelImporter(limits=limits)
    with pytest.raises(ResourceLimitError, match="exceeds maximum allowed 2"):
        importer.import_file(file_path)


def test_import_col_limit(tmp_path: Path) -> None:
    data = {"Sheet1": [["c1", "c2", "c3"], ["1", "2", "3"]]}
    file_path = tmp_path / "cols.xlsx"
    file_path.write_bytes(create_minimal_xlsx(data))

    limits = ImportLimits(max_columns=2)
    importer = ExcelImporter(limits=limits)
    with pytest.raises(ResourceLimitError, match="exceeds maximum allowed 2"):
        importer.import_file(file_path)


def test_import_corrupted_xlsx(tmp_path: Path) -> None:
    file_path = tmp_path / "corrupt.xlsx"
    file_path.write_bytes(b"PK\x03\x04not a real zip archive")

    importer = ExcelImporter()
    with pytest.raises(ParseFailureError, match="Failed to read Excel file"):
        importer.import_file(file_path)
