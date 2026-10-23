"""Unit tests for the PreviewEngine."""

from workbench.domain.dataset import ColumnMetadata, Dataset, DataType
from workbench.domain.operations import Operation
from workbench.domain.pipeline import Pipeline
from workbench.engine.preview import PreviewEngine
from workbench.engine.registry import TransformationRegistry


def test_preview_single_operation() -> None:
    cols = [
        ColumnMetadata(name="name", data_type=DataType.STRING),
        ColumnMetadata(name="city", data_type=DataType.STRING),
    ]
    rows = [("  Alice  ", "Seattle"), ("Bob", "  New York  ")]
    ds = Dataset(name="users", columns=cols, rows=rows)

    engine = PreviewEngine()
    op = Operation(name="trim_whitespace")
    preview = engine.preview_operation(ds, op, row_limit=10)

    assert preview.is_exact is True
    assert preview.before_rows[0] == ("  Alice  ", "Seattle")
    assert preview.after_rows[0] == ("Alice", "Seattle")
    assert (0, 0) in preview.modified_cells  # Alice trimmed
    assert (1, 1) in preview.modified_cells  # New York trimmed
    assert preview.rows_affected == 2


def test_preview_pipeline_matches_execution_semantics() -> None:
    """Invariant (Rule 17): Preview must agree with execution semantics."""
    cols = [
        ColumnMetadata(name="val", data_type=DataType.STRING),
        ColumnMetadata(name="num", data_type=DataType.STRING),
    ]
    rows = [
        ("  hello ", "10"),
        ("  world ", ""),
        ("  world ", ""),
    ]
    ds = Dataset(name="test", columns=cols, rows=rows)

    pipeline = Pipeline(
        steps=[
            Operation(name="trim_whitespace"),
            Operation(name="drop_duplicates"),
            Operation(
                name="fill_missing",
                columns=["num"],
                parameters={"strategy": "constant", "value": "0"},
            ),
        ]
    )

    engine = PreviewEngine()
    preview = engine.preview_pipeline(ds, pipeline, row_limit=10)

    # Execute directly via registry
    registry = TransformationRegistry()
    executed_ds, _ = registry.execute_pipeline(ds, pipeline)

    # Invariant: Preview after_rows must match executed_ds rows exactly
    _, expected_rows = executed_ds.slice_preview(start=0, limit=10)
    assert preview.after_rows == expected_rows
    assert len(preview.after_rows) == 2
    assert preview.after_rows[1] == ("world", "0")
