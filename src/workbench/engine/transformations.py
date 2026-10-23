"""Deterministic, allowlisted tabular transformations.

Invariants:
- All transformations are pure functions: Dataset in -> new Dataset out.
- Original source Datasets are never mutated.
- Operations are deterministic: identical inputs yield identical outputs.
- Never silently drop records or columns without recording counts and warnings.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any

from workbench.domain.dataset import ColumnMetadata, Dataset, DataType
from workbench.domain.errors import ExecutionFailureError, ValidationError
from workbench.domain.operations import Operation


@dataclass(frozen=True)
class OperationReport:
    """Execution telemetry and impact summary for a single transformation."""

    operation_id: str
    operation_name: str
    rows_before: int
    rows_after: int
    rows_affected: int
    columns_affected: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def transform_trim_whitespace(dataset: Dataset, op: Operation) -> tuple[Dataset, OperationReport]:
    target_cols = op.columns or dataset.column_names
    target_indices = [dataset.get_column_index(c) for c in target_cols]

    rows_affected = 0
    new_rows: list[tuple[Any, ...]] = []

    for row in dataset.rows:
        row_list = list(row)
        modified = False
        for idx in target_indices:
            val = row_list[idx]
            if isinstance(val, str):
                trimmed = val.strip()
                if trimmed != val:
                    row_list[idx] = trimmed
                    modified = True
        if modified:
            rows_affected += 1
        new_rows.append(tuple(row_list))

    new_ds = dataset.with_rows_and_columns(new_rows, list(dataset.columns))
    report = OperationReport(
        operation_id=op.id,
        operation_name=op.name,
        rows_before=dataset.row_count,
        rows_after=new_ds.row_count,
        rows_affected=rows_affected,
        columns_affected=target_cols,
    )
    return new_ds, report


def transform_normalize_headers(dataset: Dataset, op: Operation) -> tuple[Dataset, OperationReport]:
    new_columns: list[ColumnMetadata] = []
    seen: dict[str, int] = {}
    warnings: list[str] = []

    for idx, col in enumerate(dataset.columns):
        # Convert to snake_case and alphanumeric
        raw_name = col.name.strip().lower()
        cleaned = re.sub(r"[^\w\s-]", "", raw_name)
        snake = re.sub(r"[-\s]+", "_", cleaned).strip("_")
        if not snake:
            snake = f"col_{idx + 1}"

        if snake in seen:
            seen[snake] += 1
            deduped = f"{snake}_{seen[snake]}"
            warnings.append(f"Normalized column '{col.name}' duplicate renamed to '{deduped}'.")
            snake = deduped
        else:
            seen[snake] = 1

        new_columns.append(
            ColumnMetadata(name=snake, data_type=col.data_type, is_nullable=col.is_nullable)
        )

    new_ds = dataset.with_rows_and_columns(list(dataset.rows), new_columns)
    report = OperationReport(
        operation_id=op.id,
        operation_name=op.name,
        rows_before=dataset.row_count,
        rows_after=new_ds.row_count,
        rows_affected=0,
        columns_affected=[c.name for c in new_columns],
        warnings=warnings,
    )
    return new_ds, report


def transform_rename_column(dataset: Dataset, op: Operation) -> tuple[Dataset, OperationReport]:
    if not op.columns or len(op.columns) != 1:
        raise ValidationError("Operation 'rename_column' requires exactly one target column.")
    target_col = op.columns[0]
    new_name = str(op.parameters["new_name"]).strip()
    if not new_name:
        raise ValidationError("New column name cannot be empty.")
    if new_name in dataset.column_names and new_name != target_col:
        raise ValidationError(f"Column '{new_name}' already exists in dataset.")

    col_idx = dataset.get_column_index(target_col)
    new_columns = list(dataset.columns)
    old_meta = new_columns[col_idx]
    new_columns[col_idx] = ColumnMetadata(
        name=new_name, data_type=old_meta.data_type, is_nullable=old_meta.is_nullable
    )

    new_ds = dataset.with_rows_and_columns(list(dataset.rows), new_columns)
    report = OperationReport(
        operation_id=op.id,
        operation_name=op.name,
        rows_before=dataset.row_count,
        rows_after=new_ds.row_count,
        rows_affected=0,
        columns_affected=[target_col],
    )
    return new_ds, report


def transform_reorder_columns(dataset: Dataset, op: Operation) -> tuple[Dataset, OperationReport]:
    order = op.parameters.get("order")
    if not order or not isinstance(order, list):
        raise ValidationError("Operation 'reorder_columns' requires parameter 'order' (list[str]).")
    if set(order) != set(dataset.column_names) or len(order) != len(dataset.column_names):
        raise ValidationError(
            f"Provided order must contain all existing columns: {dataset.column_names}"
        )

    new_indices = [dataset.get_column_index(c) for c in order]
    new_columns = [dataset.columns[idx] for idx in new_indices]

    new_rows = [tuple(row[idx] for idx in new_indices) for row in dataset.rows]
    new_ds = dataset.with_rows_and_columns(new_rows, new_columns)
    report = OperationReport(
        operation_id=op.id,
        operation_name=op.name,
        rows_before=dataset.row_count,
        rows_after=new_ds.row_count,
        rows_affected=0,
        columns_affected=order,
    )
    return new_ds, report


def transform_cast_type(dataset: Dataset, op: Operation) -> tuple[Dataset, OperationReport]:
    target_type_str = str(op.parameters["target_type"]).lower()
    try:
        target_type = DataType(target_type_str)
    except ValueError as err:
        raise ValidationError(f"Invalid target DataType '{target_type_str}'.") from err

    error_strategy = op.parameters.get("error_strategy", "coerce_null")
    target_cols = op.columns
    if not target_cols:
        raise ValidationError("Operation 'cast_type' requires at least one column.")

    target_indices = [dataset.get_column_index(c) for c in target_cols]
    rows_affected = 0
    warnings: list[str] = []
    new_rows: list[tuple[Any, ...]] = []

    for row_idx, row in enumerate(dataset.rows):
        row_list = list(row)
        modified = False
        for idx in target_indices:
            val = row_list[idx]
            converted, changed, warn = _convert_value(val, target_type, error_strategy, row_idx)
            if warn:
                warnings.append(warn)
            if changed:
                row_list[idx] = converted
                modified = True
        if modified:
            rows_affected += 1
        new_rows.append(tuple(row_list))

    new_columns = list(dataset.columns)
    for idx in target_indices:
        col = new_columns[idx]
        new_columns[idx] = ColumnMetadata(
            name=col.name, data_type=target_type, is_nullable=col.is_nullable
        )

    new_ds = dataset.with_rows_and_columns(new_rows, new_columns)
    report = OperationReport(
        operation_id=op.id,
        operation_name=op.name,
        rows_before=dataset.row_count,
        rows_after=new_ds.row_count,
        rows_affected=rows_affected,
        columns_affected=target_cols,
        warnings=warnings[:50],  # Bound warning count
    )
    return new_ds, report


def _convert_value(
    val: Any, target_type: DataType, error_strategy: str, row_idx: int
) -> tuple[Any, bool, str | None]:
    if val is None or val == "":
        return None, True if val == "" else False, None

    try:
        if target_type == DataType.INTEGER:
            return int(float(val)), True, None
        if target_type == DataType.FLOAT:
            return float(val), True, None
        if target_type == DataType.BOOLEAN:
            s = str(val).strip().lower()
            if s in ("true", "1", "t", "yes", "y"):
                return True, True, None
            if s in ("false", "0", "f", "no", "n"):
                return False, True, None
            raise ValueError(f"Cannot cast '{val}' to boolean.")
        if target_type == DataType.STRING:
            return str(val), True, None
        if target_type in (DataType.DATE, DataType.DATETIME):
            s = str(val).strip()
            # ISO parse
            if "T" in s or " " in s:
                return datetime.fromisoformat(s).isoformat(), True, None
            return date.fromisoformat(s).isoformat(), True, None
        return val, False, None
    except Exception as err:
        if error_strategy == "raise_error":
            raise ExecutionFailureError(
                f"Row {row_idx + 1} failed cast to {target_type.value}: {err}"
            ) from err
        if error_strategy == "keep_original":
            return (
                val,
                False,
                f"Row {row_idx + 1}: failed cast to {target_type.value}; kept original.",
            )
        # default: coerce_null
        return (
            None,
            True,
            f"Row {row_idx + 1}: failed cast to {target_type.value}; coerced to null.",
        )


def transform_fill_missing(dataset: Dataset, op: Operation) -> tuple[Dataset, OperationReport]:
    strategy = op.parameters["strategy"]
    constant_val = op.parameters.get("value")
    target_cols = op.columns or dataset.column_names

    new_rows = [list(r) for r in dataset.rows]
    rows_affected_set: set[int] = set()

    for col_name in target_cols:
        col_idx = dataset.get_column_index(col_name)

        if strategy == "constant":
            for r_idx, row in enumerate(new_rows):
                if row[col_idx] is None or row[col_idx] == "":
                    row[col_idx] = constant_val
                    rows_affected_set.add(r_idx)

        elif strategy in ("mean", "median"):
            # Compute numeric mean/median on valid numbers
            nums = []
            for row in dataset.rows:
                v = row[col_idx]
                if v is not None and v != "":
                    try:
                        nums.append(float(v))
                    except (ValueError, TypeError):
                        pass
            if nums:
                fill_v = (
                    sum(nums) / len(nums) if strategy == "mean" else sorted(nums)[len(nums) // 2]
                )
                fill_v = round(fill_v, 4)
                for r_idx, row in enumerate(new_rows):
                    if row[col_idx] is None or row[col_idx] == "":
                        row[col_idx] = fill_v
                        rows_affected_set.add(r_idx)

        elif strategy == "mode":
            counts: dict[Any, int] = {}
            for row in dataset.rows:
                v = row[col_idx]
                if v is not None and v != "":
                    counts[v] = counts.get(v, 0) + 1
            if counts:
                mode_val = max(counts.items(), key=lambda item: item[1])[0]
                for r_idx, row in enumerate(new_rows):
                    if row[col_idx] is None or row[col_idx] == "":
                        row[col_idx] = mode_val
                        rows_affected_set.add(r_idx)

        elif strategy == "forward_fill":
            last_val = None
            for r_idx, row in enumerate(new_rows):
                if row[col_idx] is not None and row[col_idx] != "":
                    last_val = row[col_idx]
                elif last_val is not None:
                    row[col_idx] = last_val
                    rows_affected_set.add(r_idx)

        elif strategy == "backward_fill":
            next_val = None
            for r_idx in range(len(new_rows) - 1, -1, -1):
                row = new_rows[r_idx]
                if row[col_idx] is not None and row[col_idx] != "":
                    next_val = row[col_idx]
                elif next_val is not None:
                    row[col_idx] = next_val
                    rows_affected_set.add(r_idx)

    final_rows = [tuple(r) for r in new_rows]
    new_ds = dataset.with_rows_and_columns(final_rows, list(dataset.columns))
    report = OperationReport(
        operation_id=op.id,
        operation_name=op.name,
        rows_before=dataset.row_count,
        rows_after=new_ds.row_count,
        rows_affected=len(rows_affected_set),
        columns_affected=target_cols,
    )
    return new_ds, report


def transform_drop_duplicates(dataset: Dataset, op: Operation) -> tuple[Dataset, OperationReport]:
    subset_cols = op.columns or dataset.column_names
    subset_indices = [dataset.get_column_index(c) for c in subset_cols]
    keep = op.parameters.get("keep", "first")

    if keep not in ("first", "last"):
        raise ValidationError("Parameter 'keep' must be 'first' or 'last'.")

    rows_to_check = dataset.rows if keep == "first" else list(reversed(dataset.rows))
    seen_keys: set[tuple[Any, ...]] = set()
    kept_rows: list[tuple[Any, ...]] = []

    for row in rows_to_check:
        key = tuple(row[idx] for idx in subset_indices)
        if key not in seen_keys:
            seen_keys.add(key)
            kept_rows.append(row)

    if keep == "last":
        kept_rows.reverse()

    dropped_count = dataset.row_count - len(kept_rows)
    new_ds = dataset.with_rows_and_columns(kept_rows, list(dataset.columns))
    report = OperationReport(
        operation_id=op.id,
        operation_name=op.name,
        rows_before=dataset.row_count,
        rows_after=new_ds.row_count,
        rows_affected=dropped_count,
        columns_affected=subset_cols,
    )
    return new_ds, report


def transform_filter_rows(dataset: Dataset, op: Operation) -> tuple[Dataset, OperationReport]:
    if not op.columns or len(op.columns) != 1:
        raise ValidationError(
            "Operation 'filter_rows' requires exactly one target column in 'columns'."
        )
    col_name = op.columns[0]
    col_idx = dataset.get_column_index(col_name)

    operator = op.parameters["operator"]
    comp_value = op.parameters.get("value")

    kept_rows: list[tuple[Any, ...]] = []
    for row in dataset.rows:
        val = row[col_idx]
        if _matches_condition(val, operator, comp_value):
            kept_rows.append(row)

    dropped = dataset.row_count - len(kept_rows)
    new_ds = dataset.with_rows_and_columns(kept_rows, list(dataset.columns))
    report = OperationReport(
        operation_id=op.id,
        operation_name=op.name,
        rows_before=dataset.row_count,
        rows_after=new_ds.row_count,
        rows_affected=dropped,
        columns_affected=[col_name],
    )
    return new_ds, report


def _matches_condition(val: Any, operator: str, comp_val: Any) -> bool:
    if operator == "is_null":
        return val is None or val == ""
    if operator == "not_null":
        return val is not None and val != ""

    if val is None or val == "":
        return False

    val_str = str(val)
    comp_str = str(comp_val)

    if operator == "==":
        return val_str == comp_str
    if operator == "!=":
        return val_str != comp_str
    if operator == "contains":
        return comp_str.lower() in val_str.lower()
    if operator == "not_contains":
        return comp_str.lower() not in val_str.lower()
    if operator == "starts_with":
        return val_str.lower().startswith(comp_str.lower())
    if operator == "ends_with":
        return val_str.lower().endswith(comp_str.lower())

    # Numeric comparisons
    try:
        val_num = float(val)
        comp_num = float(comp_val)
        if operator == ">":
            return val_num > comp_num
        if operator == ">=":
            return val_num >= comp_num
        if operator == "<":
            return val_num < comp_num
        if operator == "<=":
            return val_num <= comp_num
    except (ValueError, TypeError):
        pass

    return False


def transform_drop_columns(dataset: Dataset, op: Operation) -> tuple[Dataset, OperationReport]:
    to_drop = set(op.columns)
    if not to_drop:
        raise ValidationError("Operation 'drop_columns' requires at least one column.")

    keep_indices = [
        (idx, col) for idx, col in enumerate(dataset.columns) if col.name not in to_drop
    ]
    if not keep_indices:
        raise ValidationError("Cannot drop all columns from dataset.")

    new_columns = [col for _, col in keep_indices]
    new_rows = [tuple(row[idx] for idx, _ in keep_indices) for row in dataset.rows]

    new_ds = dataset.with_rows_and_columns(new_rows, new_columns)
    report = OperationReport(
        operation_id=op.id,
        operation_name=op.name,
        rows_before=dataset.row_count,
        rows_after=new_ds.row_count,
        rows_affected=0,
        columns_affected=list(to_drop),
    )
    return new_ds, report


def transform_select_columns(dataset: Dataset, op: Operation) -> tuple[Dataset, OperationReport]:
    selected = op.columns
    if not selected:
        raise ValidationError("Operation 'select_columns' requires at least one column.")

    indices = [dataset.get_column_index(c) for c in selected]
    new_columns = [dataset.columns[idx] for idx in indices]
    new_rows = [tuple(row[idx] for idx in indices) for row in dataset.rows]

    new_ds = dataset.with_rows_and_columns(new_rows, new_columns)
    report = OperationReport(
        operation_id=op.id,
        operation_name=op.name,
        rows_before=dataset.row_count,
        rows_after=new_ds.row_count,
        rows_affected=0,
        columns_affected=selected,
    )
    return new_ds, report


def transform_split_column(dataset: Dataset, op: Operation) -> tuple[Dataset, OperationReport]:
    if not op.columns or len(op.columns) != 1:
        raise ValidationError("Operation 'split_column' requires exactly one source column.")
    source_col = op.columns[0]
    delimiter = op.parameters.get("delimiter", " ")
    new_col_names = op.parameters.get("new_columns")
    if not new_col_names or not isinstance(new_col_names, list):
        raise ValidationError("Operation 'split_column' requires 'new_columns' (list[str]).")

    source_idx = dataset.get_column_index(source_col)
    max_splits = len(new_col_names) - 1

    new_columns = []
    for idx, col in enumerate(dataset.columns):
        if idx == source_idx:
            for new_name in new_col_names:
                new_columns.append(ColumnMetadata(name=new_name, data_type=DataType.STRING))
        else:
            new_columns.append(col)

    new_rows: list[tuple[Any, ...]] = []
    for row in dataset.rows:
        val = str(row[source_idx]) if row[source_idx] is not None else ""
        parts = val.split(delimiter, max_splits)
        # Pad parts if fewer than new_columns
        parts += [""] * (len(new_col_names) - len(parts))

        row_list = list(row[:source_idx]) + parts + list(row[source_idx + 1 :])
        new_rows.append(tuple(row_list))

    new_ds = dataset.with_rows_and_columns(new_rows, new_columns)
    report = OperationReport(
        operation_id=op.id,
        operation_name=op.name,
        rows_before=dataset.row_count,
        rows_after=new_ds.row_count,
        rows_affected=dataset.row_count,
        columns_affected=new_col_names,
    )
    return new_ds, report


def transform_combine_columns(dataset: Dataset, op: Operation) -> tuple[Dataset, OperationReport]:
    if not op.columns or len(op.columns) < 2:
        raise ValidationError("Operation 'combine_columns' requires at least 2 source columns.")
    separator = op.parameters.get("separator", " ")
    new_col_name = op.parameters.get("new_column_name")
    if not new_col_name or not isinstance(new_col_name, str):
        raise ValidationError("Operation 'combine_columns' requires 'new_column_name' (str).")

    source_indices = [dataset.get_column_index(c) for c in op.columns]
    new_columns = list(dataset.columns) + [
        ColumnMetadata(name=new_col_name, data_type=DataType.STRING)
    ]

    new_rows: list[tuple[Any, ...]] = []
    for row in dataset.rows:
        vals = [str(row[idx]) for idx in source_indices if row[idx] is not None and row[idx] != ""]
        combined = separator.join(vals)
        new_rows.append(row + (combined,))

    new_ds = dataset.with_rows_and_columns(new_rows, new_columns)
    report = OperationReport(
        operation_id=op.id,
        operation_name=op.name,
        rows_before=dataset.row_count,
        rows_after=new_ds.row_count,
        rows_affected=dataset.row_count,
        columns_affected=[new_col_name],
    )
    return new_ds, report
