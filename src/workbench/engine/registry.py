"""Transformation registry and pipeline execution engine.

Invariants:
- All operations are dispatched through the allowlisted registry.
- Execution is strictly deterministic and preserves original datasets.
- Step failures preserve diagnostic context without corrupting source data.
"""

from __future__ import annotations

from collections.abc import Callable

from workbench.domain.dataset import Dataset
from workbench.domain.errors import ExecutionFailureError, ValidationError
from workbench.domain.operations import Operation, OperationName
from workbench.domain.pipeline import Pipeline
from workbench.engine.transformations import (
    OperationReport,
    transform_cast_type,
    transform_combine_columns,
    transform_drop_columns,
    transform_drop_duplicates,
    transform_fill_missing,
    transform_filter_rows,
    transform_normalize_headers,
    transform_rename_column,
    transform_reorder_columns,
    transform_select_columns,
    transform_split_column,
    transform_trim_whitespace,
)

TransformationHandler = Callable[[Dataset, Operation], tuple[Dataset, OperationReport]]


class TransformationRegistry:
    """Registry mapping allowlisted operations to pure transformation handlers."""

    def __init__(self) -> None:
        self._registry: dict[str, TransformationHandler] = {
            OperationName.TRIM_WHITESPACE.value: transform_trim_whitespace,
            OperationName.NORMALIZE_HEADERS.value: transform_normalize_headers,
            OperationName.RENAME_COLUMN.value: transform_rename_column,
            OperationName.REORDER_COLUMNS.value: transform_reorder_columns,
            OperationName.CAST_TYPE.value: transform_cast_type,
            OperationName.FILL_MISSING.value: transform_fill_missing,
            OperationName.DROP_DUPLICATES.value: transform_drop_duplicates,
            OperationName.FILTER_ROWS.value: transform_filter_rows,
            OperationName.DROP_COLUMNS.value: transform_drop_columns,
            OperationName.SELECT_COLUMNS.value: transform_select_columns,
            OperationName.SPLIT_COLUMN.value: transform_split_column,
            OperationName.COMBINE_COLUMNS.value: transform_combine_columns,
        }

    def get_handler(self, operation_name: str) -> TransformationHandler:
        if operation_name not in self._registry:
            raise ValidationError(
                f"No transformation handler registered for operation '{operation_name}'."
            )
        return self._registry[operation_name]

    def execute_operation(
        self, dataset: Dataset, operation: Operation
    ) -> tuple[Dataset, OperationReport]:
        """Apply a single operation to a dataset, returning new Dataset and report."""
        if not operation.enabled:
            noop_report = OperationReport(
                operation_id=operation.id,
                operation_name=operation.name,
                rows_before=dataset.row_count,
                rows_after=dataset.row_count,
                rows_affected=0,
                warnings=["Operation disabled; skipped."],
            )
            return dataset, noop_report

        # Check column existence before execution (except for operations like normalize_headers)
        if operation.name not in (OperationName.NORMALIZE_HEADERS.value,):
            for col in operation.columns:
                if col not in dataset.column_names:
                    raise ValidationError(
                        f"Cannot execute '{operation.name}': column '{col}' missing from dataset."
                    )

        handler = self.get_handler(operation.name)
        try:
            return handler(dataset, operation)
        except (ValidationError, ExecutionFailureError):
            raise
        except Exception as err:
            raise ExecutionFailureError(
                f"Operation '{operation.name}' failed during execution: {err}",
                details={"operation_id": operation.id, "operation_name": operation.name},
            ) from err

    def execute_pipeline(
        self, dataset: Dataset, pipeline: Pipeline
    ) -> tuple[Dataset, list[OperationReport]]:
        """Sequentially execute all enabled operations in a pipeline."""
        warnings = pipeline.validate_against_dataset(dataset)
        reports: list[OperationReport] = []
        current_ds = dataset

        for step in pipeline.steps:
            if not step.enabled:
                reports.append(
                    OperationReport(
                        operation_id=step.id,
                        operation_name=step.name,
                        rows_before=current_ds.row_count,
                        rows_after=current_ds.row_count,
                        rows_affected=0,
                        warnings=["Step is disabled."],
                    )
                )
                continue

            current_ds, step_report = self.execute_operation(current_ds, step)
            reports.append(step_report)

        if warnings:
            # Append general pipeline warnings to first report if present
            if reports:
                reports[0] = OperationReport(
                    operation_id=reports[0].operation_id,
                    operation_name=reports[0].operation_name,
                    rows_before=reports[0].rows_before,
                    rows_after=reports[0].rows_after,
                    rows_affected=reports[0].rows_affected,
                    columns_affected=reports[0].columns_affected,
                    warnings=list(reports[0].warnings) + warnings,
                )

        return current_ds, reports
