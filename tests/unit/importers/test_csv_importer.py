"""Unit tests for CsvImporter."""

import pytest

from tests.fixtures import get_fixture_path
from workbench.adapters.importers.base import ImportLimits
from workbench.adapters.importers.csv_importer import CsvImporter
from workbench.domain.errors import ParseFailureError, ResourceLimitError


def test_import_clean_sample_csv() -> None:
    importer = CsvImporter()
    path = get_fixture_path("clean_sample.csv")
    content_before = path.read_bytes()

    result = importer.import_file(path)

    assert result.dataset.name == "clean_sample"
    assert result.dataset.shape == (5, 6)
    assert result.dataset.column_names == [
        "id",
        "full_name",
        "age",
        "city",
        "signup_date",
        "active",
    ]
    assert result.detected_delimiter == ","
    assert result.detected_encoding == "utf-8"
    assert len(result.warnings) == 0

    # Invariant: Source file remains strictly unchanged
    assert path.read_bytes() == content_before


def test_import_messy_sample_csv() -> None:
    importer = CsvImporter()
    path = get_fixture_path("messy_sample.csv")

    result = importer.import_file(path)

    # Headers trimmed
    assert result.dataset.column_names == [
        "id",
        "full_name",
        "age",
        "city",
        "signup_date",
        "active",
    ]
    # Invariant: Never silently discard duplicate rows during import
    assert result.dataset.row_count == 6


def test_import_header_only_csv() -> None:
    importer = CsvImporter()
    path = get_fixture_path("header_only.csv")

    result = importer.import_file(path)

    assert result.dataset.shape == (0, 3)
    assert result.dataset.column_names == ["id", "name", "value"]


def test_import_empty_file_raises_error() -> None:
    importer = CsvImporter()
    path = get_fixture_path("empty.csv")

    with pytest.raises(ParseFailureError, match="Cannot import empty file"):
        importer.import_file(path)


def test_import_malformed_csv_permissive_and_strict() -> None:
    # Permissive mode records warnings and pads/truncates rows
    permissive_importer = CsvImporter(strict=False)
    path = get_fixture_path("malformed.csv")
    result = permissive_importer.import_file(path)

    assert len(result.warnings) > 0
    assert result.dataset.column_count == 3

    # Strict mode raises ParseFailureError on ragged row
    strict_importer = CsvImporter(strict=True)
    with pytest.raises(ParseFailureError, match="Row .* has .* values, expected 3"):
        strict_importer.import_file(path)


def test_resource_limit_file_size() -> None:
    importer = CsvImporter()
    path = get_fixture_path("clean_sample.csv")

    # Set tiny file size limit (10 bytes)
    limits = ImportLimits(max_file_size_bytes=10)
    with pytest.raises(ResourceLimitError, match="File size .* exceeds limit"):
        importer.import_file(path, limits=limits)


def test_resource_limit_max_rows() -> None:
    importer = CsvImporter()
    path = get_fixture_path("clean_sample.csv")

    # Set row limit lower than 5 rows
    limits = ImportLimits(max_rows=2)
    with pytest.raises(ResourceLimitError, match="Row count exceeded limit of 2 rows"):
        importer.import_file(path, limits=limits)


def test_resource_limit_max_columns() -> None:
    importer = CsvImporter()
    path = get_fixture_path("clean_sample.csv")

    # Set column limit lower than 6 columns
    limits = ImportLimits(max_columns=3)
    with pytest.raises(ResourceLimitError, match="Column count .* exceeds limit of 3"):
        importer.import_file(path, limits=limits)


def test_import_non_existent_file() -> None:
    importer = CsvImporter()
    with pytest.raises(ParseFailureError, match="Source file not found"):
        importer.import_file("non_existent_file_xyz123.csv")


def test_duplicate_and_empty_column_headers() -> None:
    importer = CsvImporter()
    csv_text = "col,,col\nval1,val2,val3\n"
    res = importer.import_from_string(csv_text)

    # Empty header renamed to unnamed_2, duplicate col renamed to col_2
    assert res.dataset.column_names == ["col", "unnamed_2", "col_2"]
    assert res.dataset.row_count == 1
    assert res.dataset.get_row(0) == ("val1", "val2", "val3")
