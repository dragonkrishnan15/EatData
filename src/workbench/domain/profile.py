"""Dataset and column profiling domain models.

Invariants:
- Profiles represent statistical summaries and quality indicators.
- Profiling operations NEVER mutate the source dataset.
- Metadata representations must adhere to the allowlist boundary without raw rows.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from workbench.domain.dataset import DataType


@dataclass(frozen=True)
class ColumnProfile:
    """Statistical and quality metrics for a single column."""

    name: str
    inferred_type: DataType = DataType.UNKNOWN
    type_confidence: float = 1.0
    is_uncertain: bool = False
    null_count: int = 0
    null_percentage: float = 0.0
    empty_string_count: int = 0
    distinct_count: int = 0
    is_unique: bool = False
    is_constant: bool = False
    is_empty: bool = False
    min_value: Any | None = None
    max_value: Any | None = None
    mean_value: float | None = None
    sample_categories: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        result = asdict(self)
        result["inferred_type"] = self.inferred_type.value
        return result


@dataclass(frozen=True)
class DatasetProfile:
    """Comprehensive quality and structural summary of a dataset."""

    dataset_id: str
    dataset_name: str
    row_count: int
    column_count: int
    duplicate_row_count: int
    total_null_count: int
    columns: dict[str, ColumnProfile] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)

    def get_column(self, name: str) -> ColumnProfile | None:
        return self.columns.get(name)

    def to_dict(self) -> dict[str, Any]:
        return {
            "dataset_id": self.dataset_id,
            "dataset_name": self.dataset_name,
            "row_count": self.row_count,
            "column_count": self.column_count,
            "duplicate_row_count": self.duplicate_row_count,
            "total_null_count": self.total_null_count,
            "columns": {k: v.to_dict() for k, v in self.columns.items()},
            "warnings": list(self.warnings),
        }

    def to_safe_metadata(self, alias_columns: bool = False) -> dict[str, Any]:
        """Generate safe, allowlisted metadata for optional AI assistance.

        CRITICAL PRIVACY INVARIANT:
        This output never contains raw row contents, cell values, or file paths.
        """
        col_summaries: list[dict[str, Any]] = []
        for i, (name, col) in enumerate(self.columns.items()):
            display_name = f"col_{i + 1}" if alias_columns else name
            col_summaries.append(
                {
                    "identifier": display_name,
                    "inferred_type": col.inferred_type.value,
                    "is_uncertain": col.is_uncertain,
                    "null_percentage": round(col.null_percentage, 2),
                    "distinct_count": col.distinct_count,
                    "is_constant": col.is_constant,
                    "is_empty": col.is_empty,
                    "pattern_categories": col.sample_categories,
                }
            )

        return {
            "row_count": self.row_count,
            "column_count": self.column_count,
            "duplicate_row_count": self.duplicate_row_count,
            "columns": col_summaries,
            "warnings": list(self.warnings),
        }

    def __repr__(self) -> str:
        return (
            f"DatasetProfile(id='{self.dataset_id}', rows={self.row_count}, "
            f"cols={self.column_count}, nulls={self.total_null_count}, "
            f"duplicates={self.duplicate_row_count})"
        )
