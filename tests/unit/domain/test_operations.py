"""Unit tests for the Operation domain model."""

import pytest

from workbench.domain.errors import ValidationError
from workbench.domain.operations import ALLOWLISTED_OPERATIONS, Operation, OperationName


def test_allowlisted_operations_valid() -> None:
    for op_name in ALLOWLISTED_OPERATIONS:
        # Check basic instantiation works for all allowlisted operations
        params = {}
        cols = ["col_a"]
        if op_name == OperationName.RENAME_COLUMN.value:
            params = {"new_name": "col_b"}
        elif op_name == OperationName.CAST_TYPE.value:
            params = {"target_type": "integer"}
        elif op_name == OperationName.FILL_MISSING.value:
            params = {"strategy": "constant", "value": 0}
        elif op_name == OperationName.FILTER_ROWS.value:
            params = {"condition": "greater_than", "operator": ">", "value": 10}

        op = Operation(name=op_name, columns=cols, parameters=params)
        assert op.name == op_name
        assert op.enabled is True


def test_reject_unsupported_operation() -> None:
    with pytest.raises(ValidationError, match="Unknown or disallowed operation 'drop_database'"):
        Operation(name="drop_database")

    with pytest.raises(ValidationError, match="Unknown or disallowed operation 'execute_sql'"):
        Operation(name="execute_sql")


def test_rename_column_validation() -> None:
    # Missing new_name
    with pytest.raises(ValidationError, match="requires parameter 'new_name'"):
        Operation(name="rename_column", columns=["old_col"], parameters={})

    # Multiple columns specified
    with pytest.raises(ValidationError, match="requires exactly one target column"):
        Operation(
            name="rename_column",
            columns=["col1", "col2"],
            parameters={"new_name": "renamed"},
        )


def test_fill_missing_validation() -> None:
    with pytest.raises(ValidationError, match="requires parameter 'strategy'"):
        Operation(name="fill_missing", columns=["col1"], parameters={})

    with pytest.raises(ValidationError, match="Invalid fill strategy 'magic'"):
        Operation(name="fill_missing", columns=["col1"], parameters={"strategy": "magic"})

    with pytest.raises(ValidationError, match="requires a 'value' parameter"):
        Operation(name="fill_missing", columns=["col1"], parameters={"strategy": "constant"})


def test_operation_dict_serialization() -> None:
    op = Operation(
        name="trim_whitespace",
        columns=["name", "city"],
        parameters={},
        enabled=True,
    )
    data = op.to_dict()
    assert data["name"] == "trim_whitespace"
    assert data["columns"] == ["name", "city"]
    assert data["enabled"] is True

    restored = Operation.from_dict(data)
    assert restored.name == op.name
    assert restored.columns == op.columns
    assert restored.id == op.id
