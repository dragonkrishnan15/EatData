"""Unit tests for the Profile domain model."""

from workbench.domain.dataset import DataType
from workbench.domain.profile import ColumnProfile, DatasetProfile


def test_column_profile_to_dict() -> None:
    cp = ColumnProfile(
        name="email",
        inferred_type=DataType.STRING,
        null_count=2,
        null_percentage=10.0,
        distinct_count=18,
        sample_categories=["email-like"],
    )
    data = cp.to_dict()
    assert data["name"] == "email"
    assert data["inferred_type"] == "string"
    assert data["null_count"] == 2
    assert data["sample_categories"] == ["email-like"]


def test_dataset_profile_safe_metadata_allowlist() -> None:
    """Verify that to_safe_metadata produces strict allowlisted structure without raw data."""
    cp1 = ColumnProfile(
        name="user_email",
        inferred_type=DataType.STRING,
        null_percentage=5.0,
        distinct_count=95,
        sample_categories=["email-pattern"],
    )
    cp2 = ColumnProfile(
        name="revenue",
        inferred_type=DataType.FLOAT,
        null_percentage=0.0,
        distinct_count=100,
        min_value=10.5,
        max_value=999.0,
        mean_value=250.0,
    )
    profile = DatasetProfile(
        dataset_id="ds-123",
        dataset_name="financials.csv",
        row_count=100,
        column_count=2,
        duplicate_row_count=0,
        total_null_count=5,
        columns={"user_email": cp1, "revenue": cp2},
        warnings=["Sample warning"],
    )

    metadata = profile.to_safe_metadata(alias_columns=False)
    assert metadata["row_count"] == 100
    assert metadata["column_count"] == 2
    assert metadata["duplicate_row_count"] == 0
    assert len(metadata["columns"]) == 2
    assert metadata["columns"][0]["identifier"] == "user_email"
    assert metadata["columns"][0]["pattern_categories"] == ["email-pattern"]

    # Test alias_columns privacy mode
    aliased_meta = profile.to_safe_metadata(alias_columns=True)
    assert aliased_meta["columns"][0]["identifier"] == "col_1"
    assert aliased_meta["columns"][1]["identifier"] == "col_2"
