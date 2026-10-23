"""Chart specification and visual models.

Invariants:
- Visualizations operate on local dataset aggregates.
- Misleading visualizations are prevented by checking column data suitability.
- Approximation or sampling is explicitly labeled.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any


class ChartType(StrEnum):
    """Supported chart types."""

    BAR = "bar"
    LINE = "line"
    HISTOGRAM = "histogram"
    SCATTER = "scatter"
    MISSINGNESS = "missingness"


@dataclass(frozen=True)
class ChartSpec:
    """Specification of a visual chart."""

    chart_type: ChartType
    title: str
    x_column: str | None = None
    y_column: str | None = None
    aggregation: str = "count"  # "count", "sum", "mean", "none"
    max_bins: int = 15
    is_approximate: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "chart_type": self.chart_type.value,
            "title": self.title,
            "x_column": self.x_column,
            "y_column": self.y_column,
            "aggregation": self.aggregation,
            "max_bins": self.max_bins,
            "is_approximate": self.is_approximate,
        }
