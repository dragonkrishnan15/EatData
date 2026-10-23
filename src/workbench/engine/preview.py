"""Transformation preview engine.

Invariants:
- Preview must agree with execution semantics.
- Displays before and after states with precise changed-cell coordinates.
- Clearly flags when a preview is sampled or exact.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from workbench.domain.dataset import Dataset
from workbench.domain.operations import Operation
from workbench.domain.pipeline import Pipeline
from workbench.engine.registry import OperationReport, TransformationRegistry


@dataclass(frozen=True)
class PreviewResult:
    """Detailed preview of prospective changes before applying an operation or pipeline."""

    before_columns: list[str]
    after_columns: list[str]
    before_rows: list[tuple[Any, ...]]
    after_rows: list[tuple[Any, ...]]
    modified_cells: list[tuple[int, int]]  # (row_index, col_index) in after_rows
    rows_affected: int
    is_exact: bool = True
    reports: list[OperationReport] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "before_columns": self.before_columns,
            "after_columns": self.after_columns,
            "before_rows": [list(r) for r in self.before_rows],
            "after_rows": [list(r) for r in self.after_rows],
            "modified_cells": self.modified_cells,
            "rows_affected": self.rows_affected,
            "is_exact": self.is_exact,
            "reports": [r.to_dict() for r in self.reports],
        }


class PreviewEngine:
    """Generates deterministic previews for single operations and multi-step pipelines."""

    def __init__(self, registry: TransformationRegistry | None = None) -> None:
        self.registry = registry or TransformationRegistry()

    def preview_operation(
        self,
        dataset: Dataset,
        operation: Operation,
        row_limit: int = 50,
    ) -> PreviewResult:
        """Preview prospective changes for a single operation."""
        # Execute the operation deterministically
        transformed_ds, report = self.registry.execute_operation(dataset, operation)

        # Build preview slices
        before_cols, before_slice = dataset.slice_preview(start=0, limit=row_limit)
        after_cols, after_slice = transformed_ds.slice_preview(start=0, limit=row_limit)

        # Detect modified cells within the preview slice
        modified_cells = self._compute_modified_cells(before_slice, after_slice)

        is_exact = dataset.row_count <= row_limit and transformed_ds.row_count <= row_limit

        return PreviewResult(
            before_columns=before_cols,
            after_columns=after_cols,
            before_rows=before_slice,
            after_rows=after_slice,
            modified_cells=modified_cells,
            rows_affected=report.rows_affected,
            is_exact=is_exact,
            reports=[report],
        )

    def preview_pipeline(
        self,
        dataset: Dataset,
        pipeline: Pipeline,
        row_limit: int = 50,
    ) -> PreviewResult:
        """Preview prospective changes for an entire pipeline."""
        transformed_ds, reports = self.registry.execute_pipeline(dataset, pipeline)

        before_cols, before_slice = dataset.slice_preview(start=0, limit=row_limit)
        after_cols, after_slice = transformed_ds.slice_preview(start=0, limit=row_limit)

        modified_cells = self._compute_modified_cells(before_slice, after_slice)
        total_affected = sum(r.rows_affected for r in reports)
        is_exact = dataset.row_count <= row_limit and transformed_ds.row_count <= row_limit

        return PreviewResult(
            before_columns=before_cols,
            after_columns=after_cols,
            before_rows=before_slice,
            after_rows=after_slice,
            modified_cells=modified_cells,
            rows_affected=total_affected,
            is_exact=is_exact,
            reports=reports,
        )

    def _compute_modified_cells(
        self, before_rows: list[tuple[Any, ...]], after_rows: list[tuple[Any, ...]]
    ) -> list[tuple[int, int]]:
        """Identify (row_idx, col_idx) where values differ between before and after slices."""
        modified: list[tuple[int, int]] = []
        min_rows = min(len(before_rows), len(after_rows))

        for r_idx in range(min_rows):
            b_row = before_rows[r_idx]
            a_row = after_rows[r_idx]
            min_cols = min(len(b_row), len(a_row))
            for c_idx in range(min_cols):
                if b_row[c_idx] != a_row[c_idx]:
                    modified.append((r_idx, c_idx))

        return modified
