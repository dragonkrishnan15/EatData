"""Unit tests for safe dataset exporters."""

from pathlib import Path

import pytest

from tests.fixtures import get_fixture_path
from workbench.adapters.exporters.csv_exporter import CsvExporter
from workbench.adapters.exporters.json_exporter import JsonExporter
from workbench.adapters.importers.csv_importer import CsvImporter
from workbench.adapters.importers.json_importer import JsonImporter
from workbench.domain.dataset import ColumnMetadata, Dataset, DataType
from workbench.domain.errors import ExportConflictError


@pytest.fixture
def test_dataset() -> Dataset:
    cols = [
        ColumnMetadata(name="id", data_type=DataType.INTEGER),
        ColumnMetadata(name="name", data_type=DataType.STRING),
        ColumnMetadata(name="salary", data_type=DataType.FLOAT),
    ]
    rows = [(1, "Alice", 75000.0), (2, "Bob", 62000.5)]
    return Dataset(name="employees", columns=cols, rows=rows)


def test_csv_export_roundtrip(tmp_path: Path, test_dataset: Dataset) -> None:
    exporter = CsvExporter(safe_csv_mode=False)
    out_file = tmp_path / "exported.csv"

    res = exporter.export(test_dataset, out_file)
    assert res.rows_exported == 2
    assert res.columns_exported == 3
    assert out_file.exists()

    # Import back and verify
    importer = CsvImporter()
    imported = importer.import_file(out_file).dataset
    assert imported.column_names == ["id", "name", "salary"]
    assert imported.row_count == 2
    assert imported.get_row(0) == ("1", "Alice", "75000.0")


def test_json_export_roundtrip(tmp_path: Path, test_dataset: Dataset) -> None:
    exporter = JsonExporter(layout="records")
    out_file = tmp_path / "exported.json"

    res = exporter.export(test_dataset, out_file)
    assert res.rows_exported == 2
    assert out_file.exists()

    importer = JsonImporter()
    imported = importer.import_file(out_file).dataset
    assert imported.column_names == ["id", "name", "salary"]
    assert imported.row_count == 2


def test_source_overwrite_protection(tmp_path: Path, test_dataset: Dataset) -> None:
    source_file = tmp_path / "original_source.csv"
    source_file.write_text("dummy content", encoding="utf-8")

    exporter = CsvExporter()

    # Attempting to export to the exact source path without overwrite=True must raise
    with pytest.raises(ExportConflictError, match="matches source file"):
        exporter.export(test_dataset, destination_path=source_file, source_path=source_file)

    # With overwrite=True, succeeds
    res = exporter.export(
        test_dataset,
        destination_path=source_file,
        source_path=source_file,
        overwrite=True,
    )
    assert res.rows_exported == 2


def test_destination_file_exists_conflict(tmp_path: Path, test_dataset: Dataset) -> None:
    dest_file = tmp_path / "existing.csv"
    dest_file.write_text("existing content", encoding="utf-8")

    exporter = CsvExporter()
    with pytest.raises(ExportConflictError, match="Destination file already exists"):
        exporter.export(test_dataset, destination_path=dest_file)


def test_safe_csv_formula_injection_defense(tmp_path: Path) -> None:
    """Security Invariant: Dangerous formula characters must be prefixed with ' in safe mode."""
    importer = CsvImporter()
    fixture = get_fixture_path("formula_injection.csv")
    ds = importer.import_file(fixture).dataset

    # Export with safe_csv_mode=True
    safe_out = tmp_path / "safe_export.csv"
    safe_exporter = CsvExporter(safe_csv_mode=True)
    safe_exporter.export(ds, safe_out)

    safe_text = safe_out.read_text(encoding="utf-8")
    assert "'=cmd|" in safe_text
    assert "'@SUM(" in safe_text
    assert "'+1+2" in safe_text
    assert "'-5+2" in safe_text

    # Export with safe_csv_mode=False
    raw_out = tmp_path / "raw_export.csv"
    raw_exporter = CsvExporter(safe_csv_mode=False)
    raw_exporter.export(ds, raw_out)

    raw_text = raw_out.read_text(encoding="utf-8")
    assert "=cmd|" in raw_text
    assert "'=cmd|" not in raw_text
