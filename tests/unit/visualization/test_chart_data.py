"""Unit tests for chart aggregation service."""

import pytest

from workbench.domain.dataset import ColumnMetadata, Dataset, DataType
from workbench.domain.errors import ValidationError
from workbench.visualization.chart_data import ChartDataService
from workbench.visualization.chart_spec import ChartSpec, ChartType


@pytest.fixture
def sample_dataset() -> Dataset:
    cols = [
        ColumnMetadata(name="category", data_type=DataType.STRING),
        ColumnMetadata(name="score", data_type=DataType.FLOAT),
        ColumnMetadata(name="visits", data_type=DataType.INTEGER),
    ]
    rows = [
        ("A", 10.5, 5),
        ("B", 20.0, 10),
        ("A", 15.5, 7),
        ("C", None, 0),
        ("B", 25.0, 12),
        (None, 5.0, 1),
    ]
    return Dataset(name="test_charts", columns=cols, rows=rows)


def test_missingness_chart(sample_dataset: Dataset) -> None:
    service = ChartDataService()
    spec = ChartSpec(chart_type=ChartType.MISSINGNESS, title="Missingness Test")
    data = service.build_chart_data(sample_dataset, spec)

    assert data["type"] == "missingness"
    assert data["title"] == "Missingness Test"
    assert data["labels"] == ["category", "score", "visits"]
    assert data["counts"] == [1, 1, 0]
    assert data["total_rows"] == 6
    assert data["percentages"][0] == round((1 / 6) * 100, 2)


def test_bar_chart_count(sample_dataset: Dataset) -> None:
    service = ChartDataService()
    spec = ChartSpec(
        chart_type=ChartType.BAR,
        title="Category Counts",
        x_column="category",
        aggregation="count",
    )
    data = service.build_chart_data(sample_dataset, spec)

    assert data["type"] == "bar"
    assert "A" in data["labels"]
    assert "B" in data["labels"]
    idx_a = data["labels"].index("A")
    assert data["values"][idx_a] == 2


def test_bar_chart_sum(sample_dataset: Dataset) -> None:
    service = ChartDataService()
    spec = ChartSpec(
        chart_type=ChartType.BAR,
        title="Score by Category",
        x_column="category",
        y_column="score",
        aggregation="sum",
    )
    data = service.build_chart_data(sample_dataset, spec)

    assert data["type"] == "bar"
    idx_a = data["labels"].index("A")
    assert data["values"][idx_a] == 26.0  # 10.5 + 15.5


def test_histogram(sample_dataset: Dataset) -> None:
    service = ChartDataService()
    spec = ChartSpec(
        chart_type=ChartType.HISTOGRAM,
        title="Score Distribution",
        x_column="score",
        max_bins=5,
    )
    data = service.build_chart_data(sample_dataset, spec)

    assert data["type"] == "histogram"
    assert len(data["labels"]) <= 5
    assert sum(data["counts"]) == 5  # 5 non-null scores


def test_line_chart(sample_dataset: Dataset) -> None:
    service = ChartDataService()
    spec = ChartSpec(
        chart_type=ChartType.LINE,
        title="Score Trend",
        x_column="visits",
        y_column="score",
    )
    data = service.build_chart_data(sample_dataset, spec)

    assert data["type"] == "line"
    assert len(data["labels"]) > 0
    assert len(data["values"]) == len(data["labels"])


def test_scatter_chart(sample_dataset: Dataset) -> None:
    service = ChartDataService()
    spec = ChartSpec(
        chart_type=ChartType.SCATTER,
        title="Visits vs Score",
        x_column="visits",
        y_column="score",
    )
    data = service.build_chart_data(sample_dataset, spec)

    assert data["type"] == "scatter"
    assert len(data["points"]) == 5  # 5 points with both non-null values


def test_invalid_chart_specs(sample_dataset: Dataset) -> None:
    service = ChartDataService()

    # Bar chart missing x_column
    with pytest.raises(ValidationError):
        service.build_chart_data(
            sample_dataset, ChartSpec(chart_type=ChartType.BAR, title="Test", x_column=None)
        )

    # Line chart missing y_column
    with pytest.raises(ValidationError):
        service.build_chart_data(
            sample_dataset,
            ChartSpec(chart_type=ChartType.LINE, title="Test", x_column="visits", y_column=None),
        )
