"""Unit tests for allowlisted transformations and pipeline execution."""

import pytest

from tests.fixtures import get_fixture_path
from workbench.adapters.importers.csv_importer import CsvImporter
from workbench.domain.dataset import ColumnMetadata, Dataset, DataType
from workbench.domain.operations import Operation
from workbench.domain.pipeline import Pipeline
from workbench.engine.registry import TransformationRegistry


@pytest.fixture
def sample_dataset() -> Dataset:
    cols = [
        ColumnMetadata(name="  ID  ", data_type=DataType.STRING),
        ColumnMetadata(name="Full Name", data_type=DataType.STRING),
        ColumnMetadata(name="Score", data_type=DataType.STRING),
        ColumnMetadata(name="Status", data_type=DataType.STRING),
    ]
    rows = [
        (" 1 ", " Alice Smith ", "95", "active"),
        (" 2 ", " Bob Jones ", "", "inactive"),
        (" 2 ", " Bob Jones ", "", "inactive"),
        (" 3 ", " Charlie Brown ", "82", "active"),
    ]
    return Dataset(name="grades", columns=cols, rows=rows)


def test_trim_whitespace(sample_dataset: Dataset) -> None:
    registry = TransformationRegistry()
    op = Operation(name="trim_whitespace", columns=["  ID  ", "Full Name"])

    new_ds, report = registry.execute_operation(sample_dataset, op)

    assert report.rows_affected == 4
    assert new_ds.get_row(0)[0] == "1"
    assert new_ds.get_row(0)[1] == "Alice Smith"
    # Invariant: Original dataset is unmodified
    assert sample_dataset.get_row(0)[0] == " 1 "


def test_normalize_headers(sample_dataset: Dataset) -> None:
    registry = TransformationRegistry()
    op = Operation(name="normalize_headers")

    new_ds, report = registry.execute_operation(sample_dataset, op)

    assert new_ds.column_names == ["id", "full_name", "score", "status"]
    assert sample_dataset.column_names == ["  ID  ", "Full Name", "Score", "Status"]


def test_rename_column(sample_dataset: Dataset) -> None:
    registry = TransformationRegistry()
    op = Operation(
        name="rename_column",
        columns=["Status"],
        parameters={"new_name": "account_status"},
    )

    new_ds, report = registry.execute_operation(sample_dataset, op)

    assert "account_status" in new_ds.column_names
    assert "Status" not in new_ds.column_names


def test_reorder_columns(sample_dataset: Dataset) -> None:
    registry = TransformationRegistry()
    new_order = ["Status", "Score", "Full Name", "  ID  "]
    op = Operation(name="reorder_columns", parameters={"order": new_order})

    new_ds, report = registry.execute_operation(sample_dataset, op)

    assert new_ds.column_names == new_order
    assert new_ds.get_row(0)[0] == "active"


def test_cast_type_and_error_strategy() -> None:
    cols = [ColumnMetadata(name="age", data_type=DataType.STRING)]
    rows = [("25",), ("invalid_age",), ("",)]
    ds = Dataset(name="ages", columns=cols, rows=rows)
    registry = TransformationRegistry()

    # Coerce null
    op_coerce = Operation(
        name="cast_type",
        columns=["age"],
        parameters={"target_type": "integer", "error_strategy": "coerce_null"},
    )
    new_ds, report = registry.execute_operation(ds, op_coerce)

    assert new_ds.columns[0].data_type == DataType.INTEGER
    assert new_ds.get_row(0)[0] == 25
    assert new_ds.get_row(1)[0] is None
    assert new_ds.get_row(2)[0] is None


def test_fill_missing_strategies() -> None:
    cols = [ColumnMetadata(name="val", data_type=DataType.STRING)]
    rows = [("10",), ("20",), ("",), ("40",)]
    ds = Dataset(name="num_test", columns=cols, rows=rows)
    registry = TransformationRegistry()

    # Constant
    op_const = Operation(
        name="fill_missing",
        columns=["val"],
        parameters={"strategy": "constant", "value": "0"},
    )
    new_ds, report = registry.execute_operation(ds, op_const)
    assert new_ds.get_row(2)[0] == "0"

    # Forward fill
    op_ffill = Operation(
        name="fill_missing",
        columns=["val"],
        parameters={"strategy": "forward_fill"},
    )
    new_ds2, _ = registry.execute_operation(ds, op_ffill)
    assert new_ds2.get_row(2)[0] == "20"


def test_drop_duplicates(sample_dataset: Dataset) -> None:
    registry = TransformationRegistry()
    op = Operation(name="drop_duplicates")

    new_ds, report = registry.execute_operation(sample_dataset, op)

    assert report.rows_affected == 1
    assert new_ds.row_count == 3


def test_filter_rows(sample_dataset: Dataset) -> None:
    registry = TransformationRegistry()
    op = Operation(
        name="filter_rows",
        columns=["Status"],
        parameters={"operator": "==", "value": "active"},
    )

    new_ds, report = registry.execute_operation(sample_dataset, op)

    assert new_ds.row_count == 2
    for row in new_ds.rows:
        status_idx = new_ds.get_column_index("Status")
        assert row[status_idx] == "active"


def test_drop_and_select_columns(sample_dataset: Dataset) -> None:
    registry = TransformationRegistry()

    op_drop = Operation(name="drop_columns", columns=["Score", "Status"])
    new_ds, _ = registry.execute_operation(sample_dataset, op_drop)
    assert new_ds.column_names == ["  ID  ", "Full Name"]

    op_select = Operation(name="select_columns", columns=["Full Name"])
    new_ds2, _ = registry.execute_operation(sample_dataset, op_select)
    assert new_ds2.column_names == ["Full Name"]


def test_split_and_combine_columns() -> None:
    cols = [
        ColumnMetadata(name="id", data_type=DataType.STRING),
        ColumnMetadata(name="name", data_type=DataType.STRING),
    ]
    rows = [("1", "John Doe"), ("2", "Jane Smith")]
    ds = Dataset(name="people", columns=cols, rows=rows)
    registry = TransformationRegistry()

    # Split
    op_split = Operation(
        name="split_column",
        columns=["name"],
        parameters={"delimiter": " ", "new_columns": ["first_name", "last_name"]},
    )
    split_ds, _ = registry.execute_operation(ds, op_split)
    assert split_ds.column_names == ["id", "first_name", "last_name"]
    assert split_ds.get_row(0) == ("1", "John", "Doe")

    # Combine
    op_combine = Operation(
        name="combine_columns",
        columns=["first_name", "last_name"],
        parameters={"separator": ", ", "new_column_name": "full_reversed"},
    )
    combined_ds, _ = registry.execute_operation(split_ds, op_combine)
    assert "full_reversed" in combined_ds.column_names
    assert combined_ds.get_row(0)[3] == "John, Doe"


def test_pipeline_execution_end_to_end() -> None:
    importer = CsvImporter()
    path = get_fixture_path("messy_sample.csv")
    ds = importer.import_file(path).dataset

    pipeline = Pipeline(
        name="Clean Messy Pipeline",
        steps=[
            Operation(name="trim_whitespace"),
            Operation(name="drop_duplicates"),
            Operation(
                name="filter_rows",
                columns=["city"],
                parameters={"operator": "not_null"},
            ),
        ],
    )

    registry = TransformationRegistry()
    final_ds, reports = registry.execute_pipeline(ds, pipeline)

    assert len(reports) == 3
    # Dropped 1 duplicate row (Bob Jones) and filtered out 1 null city row (Diana Prince)
    assert final_ds.row_count == 4
    # Deterministic check: rows are trimmed
    for row in final_ds.rows:
        for val in row:
            if isinstance(val, str):
                assert val == val.strip()
