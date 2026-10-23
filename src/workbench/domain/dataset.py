"""Dataset domain model and column metadata.

Invariants:
- Datasets are immutable data containers. Transformations produce new Dataset instances.
- __repr__ and __str__ MUST NEVER leak raw data rows or individual cell values.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from workbench.domain.errors import ValidationError


class DataType(StrEnum):
    """Supported data types in the workbench."""

    STRING = "string"
    INTEGER = "integer"
    FLOAT = "float"
    BOOLEAN = "boolean"
    DATE = "date"
    DATETIME = "datetime"
    NULL = "null"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class ColumnMetadata:
    """Metadata for a single column."""

    name: str
    data_type: DataType = DataType.UNKNOWN
    is_nullable: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "data_type": self.data_type.value,
            "is_nullable": self.is_nullable,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ColumnMetadata:
        dtype = data.get("data_type", DataType.UNKNOWN.value)
        try:
            parsed_type = DataType(dtype)
        except ValueError:
            parsed_type = DataType.UNKNOWN
        return cls(
            name=str(data["name"]),
            data_type=parsed_type,
            is_nullable=bool(data.get("is_nullable", True)),
        )


@dataclass(frozen=True)
class Dataset:
    """In-memory tabular dataset representation.

    Rows are stored as immutable tuples to prevent accidental in-place mutation.
    """

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = "untitled"
    columns: list[ColumnMetadata] = field(default_factory=list)
    rows: list[tuple[Any, ...]] = field(default_factory=list)

    def __post_init__(self) -> None:
        # Validate column name uniqueness
        col_names = [c.name for c in self.columns]
        if len(col_names) != len(set(col_names)):
            duplicates = [name for name in col_names if col_names.count(name) > 1]
            raise ValidationError(f"Duplicate column names detected in dataset: {set(duplicates)}")

        # Validate row length consistency
        expected_cols = len(self.columns)
        for i, row in enumerate(self.rows):
            if len(row) != expected_cols:
                raise ValidationError(
                    f"Row {i} has {len(row)} values, but dataset defines {expected_cols} columns."
                )

    @property
    def column_names(self) -> list[str]:
        return [c.name for c in self.columns]

    @property
    def row_count(self) -> int:
        return len(self.rows)

    @property
    def column_count(self) -> int:
        return len(self.columns)

    @property
    def shape(self) -> tuple[int, int]:
        return (self.row_count, self.column_count)

    def get_column_index(self, col_name: str) -> int:
        """Return the 0-based index of the column, or raise ValidationError."""
        try:
            return self.column_names.index(col_name)
        except ValueError as err:
            raise ValidationError(f"Column '{col_name}' does not exist in dataset.") from err

    def get_column_metadata(self, col_name: str) -> ColumnMetadata:
        """Return the metadata for the named column."""
        idx = self.get_column_index(col_name)
        return self.columns[idx]

    def get_column_values(self, col_name: str) -> list[Any]:
        """Extract a list of all values for the specified column."""
        col_idx = self.get_column_index(col_name)
        return [row[col_idx] for row in self.rows]

    def get_row(self, index: int) -> tuple[Any, ...]:
        """Return a single row by 0-based index."""
        if index < 0 or index >= len(self.rows):
            raise ValidationError(f"Row index {index} out of bounds (0..{len(self.rows) - 1}).")
        return self.rows[index]

    def slice_preview(
        self, start: int = 0, limit: int = 10
    ) -> tuple[list[str], list[tuple[Any, ...]]]:
        """Return a bounded preview tuple of (column_names, rows)."""
        end = min(start + max(0, limit), len(self.rows))
        return (self.column_names, self.rows[start:end])

    def with_rows_and_columns(
        self,
        rows: list[tuple[Any, ...]],
        columns: list[ColumnMetadata],
        name: str | None = None,
    ) -> Dataset:
        """Pure constructor to derive a new dataset while preserving lineage ID prefix."""
        return Dataset(
            id=str(uuid.uuid4()),
            name=name if name is not None else self.name,
            columns=columns,
            rows=rows,
        )

    def __repr__(self) -> str:
        # STRICT PRIVACY: Never expose row contents or values in string representation
        cols_summary = self.column_names
        return (
            f"Dataset(id='{self.id}', name='{self.name}', "
            f"shape={self.shape}, columns={cols_summary})"
        )

    def __str__(self) -> str:
        return f"Dataset '{self.name}' ({self.row_count} rows, {self.column_count} columns)"
