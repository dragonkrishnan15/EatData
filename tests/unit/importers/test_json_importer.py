"""Unit tests for JsonImporter."""

import pytest

from tests.fixtures import get_fixture_path
from workbench.adapters.importers.base import ImportLimits
from workbench.adapters.importers.json_importer import JsonImporter
from workbench.domain.errors import ParseFailureError, ResourceLimitError


def test_import_clean_sample_json() -> None:
    importer = JsonImporter()
    path = get_fixture_path("clean_sample.json")
    content_before = path.read_bytes()

    result = importer.import_file(path)

    assert result.dataset.name == "clean_sample"
    assert result.dataset.shape == (3, 5)
    assert "id" in result.dataset.column_names
    assert "product" in result.dataset.column_names
    assert "price" in result.dataset.column_names
    assert "in_stock" in result.dataset.column_names
    assert "tags" in result.dataset.column_names

    # Source file remains unchanged
    assert path.read_bytes() == content_before


def test_import_nested_sample_json() -> None:
    importer = JsonImporter()
    path = get_fixture_path("nested_sample.json")

    result = importer.import_file(path)

    assert result.dataset.row_count == 1
    # Check that nested fields are flattened
    col_names = result.dataset.column_names
    assert "order_id" in col_names
    assert "customer.name" in col_names
    assert "customer.address.city" in col_names
    assert "customer.address.geo.lat" in col_names
    assert "items" in col_names

    # Check extracted values
    city_idx = result.dataset.get_column_index("customer.address.city")
    assert result.dataset.rows[0][city_idx] == "Denver"


def test_import_json_lines_ndjson() -> None:
    importer = JsonImporter()
    ndjson_data = '{"id": 101, "name": "Item A"}\n{"id": 102, "name": "Item B"}\n'

    result = importer.import_from_string(ndjson_data)

    assert result.dataset.shape == (2, 2)
    assert result.dataset.column_names == ["id", "name"]
    assert result.dataset.get_column_values("id") == [101, 102]


def test_import_root_keyed_json() -> None:
    importer = JsonImporter()
    wrapped_data = (
        '{"status": "ok", "items": [{"id": 1, "title": "First"}, {"id": 2, "title": "Second"}]}'
    )

    result = importer.import_from_string(wrapped_data)

    assert result.dataset.shape == (2, 2)
    assert result.dataset.column_names == ["id", "title"]


def test_import_malformed_json_raises_error() -> None:
    importer = JsonImporter()
    path = get_fixture_path("malformed.json")

    with pytest.raises(ParseFailureError, match="Failed to parse JSON content"):
        importer.import_file(path)


def test_import_empty_json_raises_error() -> None:
    importer = JsonImporter()
    with pytest.raises(ParseFailureError, match="JSON content is empty"):
        importer.import_from_string("   ")


def test_json_nesting_depth_limit() -> None:
    importer = JsonImporter()
    # Create deeply nested object: a.b.c.d.e
    deep_json = '{"a": {"b": {"c": {"d": {"e": "deep_val"}}}}}'

    # Allow max_depth = 3 -> nesting exceeds depth
    limits = ImportLimits(max_json_depth=3)
    with pytest.raises(ResourceLimitError, match="nesting depth exceeded limit"):
        importer.import_from_string(deep_json, limits=limits)


def test_json_row_limit() -> None:
    importer = JsonImporter()
    data = '[{"id": 1}, {"id": 2}, {"id": 3}, {"id": 4}]'

    limits = ImportLimits(max_rows=2)
    with pytest.raises(ResourceLimitError, match="Row count .* exceeds limit of 2"):
        importer.import_from_string(data, limits=limits)
