"""Deterministic local data profiler.

Invariants:
- Profiling operations NEVER mutate the source dataset.
- Distinguishes actual nulls, empty strings, invalid values, and zeros.
- Type inference is a hypothesis; records confidence and uncertainty.
- Computes aggregate metrics locally without network or external tools.
"""

from __future__ import annotations

import re
from datetime import date, datetime
from typing import Any

from workbench.domain.dataset import Dataset, DataType
from workbench.domain.profile import ColumnProfile, DatasetProfile

_DATE_ISO_REGEX = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_DATETIME_ISO_REGEX = re.compile(r"^\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}(:\d{2})?")
_EMAIL_REGEX = re.compile(r"^[\w\.-]+@[\w\.-]+\.\w+$")
_URL_REGEX = re.compile(r"^https?://")
_UUID_REGEX = re.compile(r"^[0-9a-fA-F-]{36}$")


class Profiler:
    """Computes comprehensive statistical and data quality profiles for Datasets."""

    def profile(self, dataset: Dataset) -> DatasetProfile:
        """Analyze a dataset and return an immutable DatasetProfile."""
        col_profiles: dict[str, ColumnProfile] = {}
        total_null_count = 0
        warnings: list[str] = []

        # Calculate duplicate rows
        seen_rows: set[tuple[Any, ...]] = set()
        duplicate_row_count = 0
        for row in dataset.rows:
            if row in seen_rows:
                duplicate_row_count += 1
            else:
                seen_rows.add(row)

        for col_name in dataset.column_names:
            values = dataset.get_column_values(col_name)
            col_prof, col_nulls, col_warnings = self._profile_column(col_name, values)
            col_profiles[col_name] = col_prof
            total_null_count += col_nulls
            warnings.extend(col_warnings)

        return DatasetProfile(
            dataset_id=dataset.id,
            dataset_name=dataset.name,
            row_count=dataset.row_count,
            column_count=dataset.column_count,
            duplicate_row_count=duplicate_row_count,
            total_null_count=total_null_count,
            columns=col_profiles,
            warnings=warnings,
        )

    def _profile_column(
        self, col_name: str, values: list[Any]
    ) -> tuple[ColumnProfile, int, list[str]]:
        total_count = len(values)
        if total_count == 0:
            return (
                ColumnProfile(
                    name=col_name,
                    inferred_type=DataType.UNKNOWN,
                    is_empty=True,
                ),
                0,
                [],
            )

        null_count = 0
        empty_string_count = 0
        non_empty_values: list[Any] = []
        warnings: list[str] = []

        for val in values:
            if val is None or val == "":
                if val is None:
                    null_count += 1
                else:
                    empty_string_count += 1
            else:
                non_empty_values.append(val)

        non_empty_count = len(non_empty_values)
        null_percentage = ((null_count + empty_string_count) / total_count) * 100.0

        if non_empty_count == 0:
            return (
                ColumnProfile(
                    name=col_name,
                    inferred_type=DataType.NULL,
                    null_count=null_count,
                    null_percentage=100.0,
                    empty_string_count=empty_string_count,
                    distinct_count=0,
                    is_empty=True,
                    is_constant=True,
                ),
                null_count + empty_string_count,
                [f"Column '{col_name}' contains only null or empty values."],
            )

        # Distinct value calculation
        distinct_vals = set(non_empty_values)
        distinct_count = len(distinct_vals)
        is_unique = distinct_count == total_count
        is_constant = distinct_count == 1

        # Type inference
        inferred_type, confidence, is_uncertain, sample_categories = self._infer_type_and_patterns(
            non_empty_values
        )

        # Numeric statistics if numeric type
        min_val: Any | None = None
        max_val: Any | None = None
        mean_val: float | None = None

        if inferred_type in (DataType.INTEGER, DataType.FLOAT):
            num_vals: list[float] = []
            for v in non_empty_values:
                try:
                    num_vals.append(float(v))
                except (ValueError, TypeError):
                    pass
            if num_vals:
                min_val = min(num_vals)
                max_val = max(num_vals)
                mean_val = round(sum(num_vals) / len(num_vals), 4)

        if is_uncertain:
            warnings.append(
                f"Column '{col_name}' has mixed types; inferred as '{inferred_type.value}' "
                f"with confidence {round(confidence * 100, 1)}%."
            )

        col_profile = ColumnProfile(
            name=col_name,
            inferred_type=inferred_type,
            type_confidence=confidence,
            is_uncertain=is_uncertain,
            null_count=null_count,
            null_percentage=round(null_percentage, 2),
            empty_string_count=empty_string_count,
            distinct_count=distinct_count,
            is_unique=is_unique,
            is_constant=is_constant,
            is_empty=False,
            min_value=min_val,
            max_value=max_val,
            mean_value=mean_val,
            sample_categories=sample_categories,
        )

        return col_profile, null_count + empty_string_count, warnings

    def _infer_type_and_patterns(
        self, non_empty_values: list[Any]
    ) -> tuple[DataType, float, bool, list[str]]:
        total = len(non_empty_values)
        int_count = 0
        float_count = 0
        bool_count = 0
        date_count = 0
        categories: set[str] = set()

        for v in non_empty_values:
            val_str = str(v).strip()

            # Boolean check
            if val_str.lower() in ("true", "false", "t", "f", "yes", "no"):
                bool_count += 1
                continue

            # Integer check
            if re.match(r"^-?\d+$", val_str):
                int_count += 1
                continue

            # Float check
            try:
                float(val_str)
                float_count += 1
                continue
            except ValueError:
                pass

            # Date check
            if _DATE_ISO_REGEX.match(val_str):
                try:
                    date.fromisoformat(val_str)
                    date_count += 1
                    categories.add("date-iso")
                    continue
                except ValueError:
                    pass

            if _DATETIME_ISO_REGEX.match(val_str):
                try:
                    datetime.fromisoformat(val_str)
                    date_count += 1
                    categories.add("datetime-iso")
                    continue
                except ValueError:
                    pass

            # Pattern classifications
            if _EMAIL_REGEX.match(val_str):
                categories.add("email-pattern")
            elif _URL_REGEX.match(val_str):
                categories.add("url-pattern")
            elif _UUID_REGEX.match(val_str):
                categories.add("uuid-pattern")

        # Determine dominant type
        if bool_count > 0 and (bool_count / total) >= 0.5:
            conf = bool_count / total
            return DataType.BOOLEAN, conf, conf < 1.0, list(categories)

        if int_count > 0 and (int_count / total) >= 0.5:
            conf = int_count / total
            return DataType.INTEGER, conf, conf < 1.0, list(categories)

        if (int_count + float_count) > 0 and ((int_count + float_count) / total) >= 0.5:
            conf = (int_count + float_count) / total
            return DataType.FLOAT, conf, conf < 1.0, list(categories)

        if date_count > 0 and (date_count / total) >= 0.5:
            conf = date_count / total
            return DataType.DATE, conf, conf < 1.0, list(categories)

        # Default is String; check if mixed types exist
        mixed = 0 < (int_count + float_count + bool_count + date_count) < total
        return DataType.STRING, 1.0, mixed, list(categories)
