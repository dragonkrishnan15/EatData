"""Unit tests for metadata package builder and column aliasing."""

import pytest

from workbench.adapters.ai.metadata import MetadataPackageBuilder
from workbench.domain.dataset import ColumnMetadata, Dataset, DataType
from workbench.domain.errors import SecurityError
from workbench.engine.profiler import Profiler


@pytest.fixture
def sample_profile():
    cols = [
        ColumnMetadata(name="user_email", data_type=DataType.STRING),
        ColumnMetadata(name="birth_date", data_type=DataType.DATE),
        ColumnMetadata(name="balance", data_type=DataType.FLOAT),
    ]
    rows = [
        ("alice@example.com", "1990-05-15", 1500.50),
        ("bob@example.com", "1985-11-20", 2400.00),
    ]
    ds = Dataset(name="sensitive_customers", columns=cols, rows=rows)
    return Profiler().profile(ds)


def test_metadata_package_builder_basic(sample_profile) -> None:
    builder = MetadataPackageBuilder()
    pkg = builder.build(sample_profile, alias_columns=False)

    assert pkg.row_count == 2
    assert pkg.column_count == 3
    assert not pkg.is_aliased
    assert len(pkg.columns) == 3

    col_names = [c.name for c in pkg.columns]
    assert "user_email" in col_names
    assert "birth_date" in col_names
    assert "balance" in col_names

    # Check payload JSON is valid and deterministic
    assert len(pkg.payload_hash) == 64
    assert "rows" not in pkg.payload_dict


def test_metadata_package_builder_aliased(sample_profile) -> None:
    builder = MetadataPackageBuilder()
    pkg = builder.build(sample_profile, alias_columns=True)

    assert pkg.is_aliased
    assert pkg.alias_mapping is not None
    assert pkg.alias_mapping["user_email"] == "col_1"
    assert pkg.alias_mapping["birth_date"] == "col_2"
    assert pkg.alias_mapping["balance"] == "col_3"

    col_names = [c.name for c in pkg.columns]
    assert col_names == ["col_1", "col_2", "col_3"]

    # Test unaliasing a recipe
    aliased_recipe = {
        "name": "Clean Pipeline",
        "version": "1.0",
        "steps": [
            {"name": "trim_whitespace", "columns": ["col_1", "col_2"], "parameters": {}},
            {
                "name": "rename_column",
                "columns": ["col_3"],
                "parameters": {"new_name": "net_balance"},
            },
        ],
    }

    unaliased = builder.unalias_recipe_dict(aliased_recipe, pkg.alias_mapping)
    assert unaliased["steps"][0]["columns"] == ["user_email", "birth_date"]
    assert unaliased["steps"][1]["columns"] == ["balance"]


def test_prohibited_keys_raise_security_error() -> None:
    builder = MetadataPackageBuilder()
    leaky_payload = {
        "schema_version": "1.0",
        "columns": [],
        "sample_values": ["leaked_secret"],
    }
    with pytest.raises(SecurityError, match="Privacy violation: prohibited key"):
        builder._verify_privacy_invariants(leaky_payload)
