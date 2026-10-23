"""Unit tests for the Profiler engine."""

from tests.fixtures import get_fixture_path
from workbench.adapters.importers.csv_importer import CsvImporter
from workbench.domain.dataset import ColumnMetadata, Dataset, DataType
from workbench.engine.profiler import Profiler


def test_profile_clean_sample() -> None:
    importer = CsvImporter()
    path = get_fixture_path("clean_sample.csv")
    import_res = importer.import_file(path)
    dataset = import_res.dataset
    original_rows = list(dataset.rows)

    profiler = Profiler()
    profile = profiler.profile(dataset)

    # Invariant: Source dataset is NEVER mutated during profiling
    assert dataset.rows == original_rows

    assert profile.row_count == 5
    assert profile.column_count == 6
    assert profile.duplicate_row_count == 0
    assert profile.total_null_count == 0

    # Column type inferences
    age_col = profile.get_column("age")
    assert age_col is not None
    assert age_col.inferred_type == DataType.INTEGER
    assert age_col.min_value == 28.0
    assert age_col.max_value == 52.0
    assert age_col.mean_value == 38.0

    active_col = profile.get_column("active")
    assert active_col is not None
    assert active_col.inferred_type == DataType.BOOLEAN

    date_col = profile.get_column("signup_date")
    assert date_col is not None
    assert date_col.inferred_type == DataType.DATE
    assert "date-iso" in date_col.sample_categories


def test_profile_messy_sample() -> None:
    importer = CsvImporter()
    path = get_fixture_path("messy_sample.csv")
    import_res = importer.import_file(path)
    dataset = import_res.dataset

    profiler = Profiler()
    profile = profiler.profile(dataset)

    assert profile.row_count == 6
    # 1 duplicate row present in messy_sample.csv (Bob Jones row)
    assert profile.duplicate_row_count == 1
    assert profile.total_null_count > 0

    city_col = profile.get_column("city")
    assert city_col is not None
    # Diana Prince has empty city
    assert city_col.empty_string_count > 0


def test_profile_empty_and_constant_columns() -> None:
    cols = [
        ColumnMetadata(name="empty_col", data_type=DataType.STRING),
        ColumnMetadata(name="constant_col", data_type=DataType.STRING),
        ColumnMetadata(name="mixed_col", data_type=DataType.STRING),
    ]
    rows = [
        ("", "fixed", "10"),
        ("", "fixed", "20"),
        ("", "fixed", "not_a_number"),
    ]
    ds = Dataset(name="test_ds", columns=cols, rows=rows)

    profiler = Profiler()
    profile = profiler.profile(ds)

    empty_col = profile.get_column("empty_col")
    assert empty_col is not None
    assert empty_col.is_empty is True

    const_col = profile.get_column("constant_col")
    assert const_col is not None
    assert const_col.is_constant is True

    mixed_col = profile.get_column("mixed_col")
    assert mixed_col is not None
    # 2 out of 3 are ints, so inferred as int but uncertain
    assert mixed_col.is_uncertain is True
    assert len(profile.warnings) > 0
