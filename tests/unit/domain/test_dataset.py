"""Unit tests for the Dataset domain model."""

import pytest

from workbench.domain.dataset import ColumnMetadata, Dataset, DataType
from workbench.domain.errors import ValidationError


def test_dataset_creation_and_properties() -> None:
    cols = [
        ColumnMetadata(name="id", data_type=DataType.INTEGER, is_nullable=False),
        ColumnMetadata(name="name", data_type=DataType.STRING),
    ]
    rows = [(1, "Alice"), (2, "Bob")]
    dataset = Dataset(name="users", columns=cols, rows=rows)

    assert dataset.name == "users"
    assert dataset.row_count == 2
    assert dataset.column_count == 2
    assert dataset.shape == (2, 2)
    assert dataset.column_names == ["id", "name"]
    assert dataset.get_column_values("id") == [1, 2]
    assert dataset.get_column_values("name") == ["Alice", "Bob"]
    assert dataset.get_row(0) == (1, "Alice")


def test_duplicate_column_detection() -> None:
    cols = [
        ColumnMetadata(name="col", data_type=DataType.STRING),
        ColumnMetadata(name="col", data_type=DataType.INTEGER),
    ]
    with pytest.raises(ValidationError, match="Duplicate column names"):
        Dataset(name="invalid", columns=cols, rows=[])


def test_inconsistent_row_length_detection() -> None:
    cols = [
        ColumnMetadata(name="c1", data_type=DataType.STRING),
        ColumnMetadata(name="c2", data_type=DataType.STRING),
    ]
    # Row 1 has only 1 value instead of 2
    rows = [("v1", "v2"), ("v3",)]
    with pytest.raises(ValidationError, match="Row 1 has 1 values, but dataset defines 2 columns"):
        Dataset(name="invalid", columns=cols, rows=rows)


def test_column_metadata_dict_roundtrip() -> None:
    meta = ColumnMetadata(name="age", data_type=DataType.INTEGER, is_nullable=False)
    data = meta.to_dict()
    assert data == {"name": "age", "data_type": "integer", "is_nullable": False}
    restored = ColumnMetadata.from_dict(data)
    assert restored == meta


def test_slice_preview() -> None:
    cols = [ColumnMetadata(name="num", data_type=DataType.INTEGER)]
    rows = [(i,) for i in range(20)]
    dataset = Dataset(columns=cols, rows=rows)

    c_names, preview_rows = dataset.slice_preview(start=5, limit=5)
    assert c_names == ["num"]
    assert len(preview_rows) == 5
    assert preview_rows[0] == (5,)
    assert preview_rows[-1] == (9,)


def test_dataset_repr_privacy_invariant() -> None:
    """CRITICAL: Dataset __repr__ and __str__ must NEVER leak cell values."""
    secret_value = "SUPER_CONFIDENTIAL_SSN_987654321"
    cols = [ColumnMetadata(name="secret", data_type=DataType.STRING)]
    rows = [(secret_value,)]
    dataset = Dataset(name="sensitive", columns=cols, rows=rows)

    repr_str = repr(dataset)
    str_str = str(dataset)

    assert secret_value not in repr_str
    assert secret_value not in str_str
    assert "Dataset" in repr_str
    assert "sensitive" in repr_str
