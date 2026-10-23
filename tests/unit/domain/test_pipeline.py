"""Unit tests for the Pipeline domain model."""

import pytest

from workbench.domain.dataset import ColumnMetadata, Dataset, DataType
from workbench.domain.errors import ValidationError
from workbench.domain.operations import Operation
from workbench.domain.pipeline import Pipeline


def test_pipeline_step_manipulation() -> None:
    pipeline = Pipeline(name="Test Pipeline")
    op1 = Operation(name="trim_whitespace", columns=["c1"])
    op2 = Operation(name="rename_column", columns=["c1"], parameters={"new_name": "c1_clean"})

    # Add steps
    pipeline = pipeline.add_step(op1).add_step(op2)
    assert len(pipeline.steps) == 2
    assert pipeline.steps[0].id == op1.id
    assert pipeline.steps[1].id == op2.id

    # Reorder steps
    pipeline = pipeline.reorder_step(0, 1)
    assert pipeline.steps[0].id == op2.id
    assert pipeline.steps[1].id == op1.id

    # Toggle step
    pipeline = pipeline.toggle_step(op1.id, enabled=False)
    assert pipeline.steps[1].enabled is False

    # Remove step
    pipeline = pipeline.remove_step(op1.id)
    assert len(pipeline.steps) == 1
    assert pipeline.steps[0].id == op2.id


def test_pipeline_validation_against_dataset() -> None:
    cols = [ColumnMetadata(name="col_x", data_type=DataType.STRING)]
    dataset = Dataset(name="ds", columns=cols, rows=[("val",)])

    # Valid step
    valid_op = Operation(name="trim_whitespace", columns=["col_x"])
    # Invalid step referring to non-existent column
    invalid_op = Operation(name="trim_whitespace", columns=["non_existent_col"])

    p = Pipeline(steps=[valid_op, invalid_op])
    warnings = p.validate_against_dataset(dataset)

    assert len(warnings) == 1
    assert "references column 'non_existent_col' missing from dataset" in warnings[0]


def test_pipeline_validation_tracks_renames() -> None:
    cols = [ColumnMetadata(name="old_name", data_type=DataType.STRING)]
    dataset = Dataset(name="ds", columns=cols, rows=[("val",)])

    step1 = Operation(
        name="rename_column",
        columns=["old_name"],
        parameters={"new_name": "new_name"},
    )
    step2 = Operation(name="trim_whitespace", columns=["new_name"])

    p = Pipeline(steps=[step1, step2])
    warnings = p.validate_against_dataset(dataset)
    assert len(warnings) == 0


def test_pipeline_json_serialization() -> None:
    op = Operation(name="trim_whitespace", columns=["c1"])
    pipeline = Pipeline(name="Serialization Test", steps=[op])

    json_str = pipeline.to_json()
    restored = Pipeline.from_json(json_str)

    assert restored.id == pipeline.id
    assert restored.name == pipeline.name
    assert len(restored.steps) == 1
    assert restored.steps[0].name == "trim_whitespace"
    assert restored.steps[0].columns == ["c1"]


def test_pipeline_invalid_json() -> None:
    with pytest.raises(ValidationError, match="Failed to parse pipeline JSON"):
        Pipeline.from_json("invalid json {[[")

    with pytest.raises(ValidationError, match="Pipeline JSON root must be an object"):
        Pipeline.from_json('["not", "an", "object"]')
