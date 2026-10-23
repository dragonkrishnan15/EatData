"""Local chart data aggregation service.

Invariants:
- Generates bounded, pre-aggregated visualization data without sending raw rows.
- Clearly flags when a chart is approximate or sampled.
"""

from __future__ import annotations

import math
from typing import Any

from workbench.domain.dataset import Dataset
from workbench.domain.errors import ValidationError
from workbench.visualization.chart_spec import ChartSpec, ChartType


class ChartDataService:
    """Computes aggregated chart payloads for visualization."""

    def build_chart_data(self, dataset: Dataset, spec: ChartSpec) -> dict[str, Any]:
        """Dispatch chart aggregation according to ChartSpec."""
        if spec.chart_type == ChartType.MISSINGNESS:
            return self.build_missingness_chart(dataset, spec.title)
        if spec.chart_type == ChartType.BAR:
            if not spec.x_column:
                raise ValidationError("Bar chart requires x_column.")
            return self.build_bar_chart(
                dataset,
                x_col=spec.x_column,
                y_col=spec.y_column,
                agg=spec.aggregation,
                title=spec.title,
                limit=spec.max_bins,
            )
        if spec.chart_type == ChartType.HISTOGRAM:
            if not spec.x_column:
                raise ValidationError("Histogram requires x_column.")
            return self.build_histogram(
                dataset,
                col_name=spec.x_column,
                bins=spec.max_bins,
                title=spec.title,
            )
        if spec.chart_type == ChartType.LINE:
            if not spec.x_column or not spec.y_column:
                raise ValidationError("Line chart requires both x_column and y_column.")
            return self.build_line_chart(
                dataset,
                x_col=spec.x_column,
                y_col=spec.y_column,
                title=spec.title,
            )
        if spec.chart_type == ChartType.SCATTER:
            if not spec.x_column or not spec.y_column:
                raise ValidationError("Scatter plot requires both x_column and y_column.")
            return self.build_scatter(
                dataset,
                x_col=spec.x_column,
                y_col=spec.y_column,
                title=spec.title,
            )

        raise ValidationError(f"Unsupported chart type: {spec.chart_type}")

    def build_missingness_chart(
        self, dataset: Dataset, title: str = "Missing Values Overview"
    ) -> dict[str, Any]:
        labels: list[str] = []
        null_counts: list[int] = []
        null_percentages: list[float] = []

        for name in dataset.column_names:
            vals = dataset.get_column_values(name)
            nulls = sum(1 for v in vals if v is None or v == "")
            pct = (nulls / dataset.row_count * 100.0) if dataset.row_count > 0 else 0.0
            labels.append(name)
            null_counts.append(nulls)
            null_percentages.append(round(pct, 2))

        return {
            "type": "missingness",
            "title": title,
            "labels": labels,
            "counts": null_counts,
            "percentages": null_percentages,
            "total_rows": dataset.row_count,
            "is_approximate": False,
        }

    def build_bar_chart(
        self,
        dataset: Dataset,
        x_col: str,
        y_col: str | None = None,
        agg: str = "count",
        title: str = "Bar Chart",
        limit: int = 25,
    ) -> dict[str, Any]:
        x_idx = dataset.get_column_index(x_col)
        categories: dict[str, float] = {}

        if agg == "count" or y_col is None:
            for row in dataset.rows:
                v = str(row[x_idx]) if row[x_idx] not in (None, "") else "(null)"
                categories[v] = categories.get(v, 0.0) + 1.0
        else:
            y_idx = dataset.get_column_index(y_col)
            counts: dict[str, int] = {}
            for row in dataset.rows:
                k = str(row[x_idx]) if row[x_idx] not in (None, "") else "(null)"
                try:
                    val = float(row[y_idx])
                    categories[k] = categories.get(k, 0.0) + val
                    counts[k] = counts.get(k, 0) + 1
                except (ValueError, TypeError):
                    continue

            if agg == "mean":
                for k in categories:
                    if counts[k] > 0:
                        categories[k] = round(categories[k] / counts[k], 4)

        # Sort by value descending and cap by limit
        sorted_items = sorted(categories.items(), key=lambda it: it[1], reverse=True)[:limit]
        labels = [k for k, _ in sorted_items]
        values = [round(v, 2) for _, v in sorted_items]

        return {
            "type": "bar",
            "title": title,
            "labels": labels,
            "values": values,
            "x_axis": x_col,
            "y_axis": y_col or "Count",
            "is_approximate": len(categories) > limit,
        }

    def build_histogram(
        self,
        dataset: Dataset,
        col_name: str,
        bins: int = 10,
        title: str = "Histogram",
    ) -> dict[str, Any]:
        vals = dataset.get_column_values(col_name)
        nums: list[float] = []
        for v in vals:
            if v not in (None, ""):
                try:
                    nums.append(float(v))
                except (ValueError, TypeError):
                    continue

        if not nums:
            return {
                "type": "histogram",
                "title": title,
                "labels": [],
                "counts": [],
                "is_approximate": False,
            }

        min_val = min(nums)
        max_val = max(nums)
        if min_val == max_val:
            return {
                "type": "histogram",
                "title": title,
                "labels": [f"{min_val}"],
                "counts": [len(nums)],
                "is_approximate": False,
            }

        bin_width = (max_val - min_val) / bins
        bin_counts = [0] * bins
        bin_edges = [min_val + i * bin_width for i in range(bins + 1)]

        for n in nums:
            b_idx = min(int((n - min_val) / bin_width), bins - 1)
            bin_counts[b_idx] += 1

        labels = [f"{round(bin_edges[i], 1)} - {round(bin_edges[i + 1], 1)}" for i in range(bins)]

        return {
            "type": "histogram",
            "title": title,
            "labels": labels,
            "counts": bin_counts,
            "min_val": round(min_val, 2),
            "max_val": round(max_val, 2),
            "is_approximate": False,
        }

    def build_line_chart(
        self,
        dataset: Dataset,
        x_col: str,
        y_col: str,
        title: str = "Line Chart",
    ) -> dict[str, Any]:
        x_idx = dataset.get_column_index(x_col)
        y_idx = dataset.get_column_index(y_col)

        points: list[tuple[Any, float]] = []
        for row in dataset.rows:
            xv = row[x_idx]
            yv = row[y_idx]
            if xv not in (None, "") and yv not in (None, ""):
                try:
                    points.append((xv, float(yv)))
                except (ValueError, TypeError):
                    continue

        # Sort by x if sortable
        try:
            points.sort(key=lambda p: p[0])
        except TypeError:
            pass

        labels = [str(p[0]) for p in points]
        values = [round(p[1], 2) for p in points]

        return {
            "type": "line",
            "title": title,
            "labels": labels,
            "values": values,
            "x_axis": x_col,
            "y_axis": y_col,
            "is_approximate": False,
        }

    def build_scatter(
        self,
        dataset: Dataset,
        x_col: str,
        y_col: str,
        title: str = "Scatter Plot",
        sample_limit: int = 500,
    ) -> dict[str, Any]:
        x_idx = dataset.get_column_index(x_col)
        y_idx = dataset.get_column_index(y_col)

        points: list[dict[str, float]] = []
        for row in dataset.rows:
            try:
                xv = float(row[x_idx])
                yv = float(row[y_idx])
                if not (math.isnan(xv) or math.isnan(yv)):
                    points.append({"x": round(xv, 4), "y": round(yv, 4)})
            except (ValueError, TypeError):
                continue

        is_approx = len(points) > sample_limit
        if is_approx:
            step = max(1, len(points) // sample_limit)
            points = points[::step][:sample_limit]

        return {
            "type": "scatter",
            "title": title,
            "points": points,
            "x_axis": x_col,
            "y_axis": y_col,
            "is_approximate": is_approx,
        }
