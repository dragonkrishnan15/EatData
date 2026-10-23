"""Operation domain model and allowlist registry.

Invariants:
- All operations are strictly allowlisted. Unknown operations are rejected.
- Operations declare name, version, target columns, parameters, and enabled status.
- Operations never execute arbitrary shell or python code.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from workbench.domain.errors import ValidationError


class OperationName(StrEnum):
    """Allowlist of supported transformation operations."""

    TRIM_WHITESPACE = "trim_whitespace"
    NORMALIZE_HEADERS = "normalize_headers"
    RENAME_COLUMN = "rename_column"
    REORDER_COLUMNS = "reorder_columns"
    CAST_TYPE = "cast_type"
    PARSE_DATE = "parse_date"
    FILL_MISSING = "fill_missing"
    DROP_DUPLICATES = "drop_duplicates"
    FILTER_ROWS = "filter_rows"
    DROP_COLUMNS = "drop_columns"
    SELECT_COLUMNS = "select_columns"
    SPLIT_COLUMN = "split_column"
    COMBINE_COLUMNS = "combine_columns"


ALLOWLISTED_OPERATIONS = frozenset(op.value for op in OperationName)


@dataclass(frozen=True)
class Operation:
    """A typed, allowlisted transformation step."""

    name: str
    columns: list[str] = field(default_factory=list)
    parameters: dict[str, Any] = field(default_factory=dict)
    version: str = "1.0"
    enabled: bool = True
    id: str = field(default_factory=lambda: str(uuid.uuid4()))

    def __post_init__(self) -> None:
        # Validate operation name against strict allowlist
        if self.name not in ALLOWLISTED_OPERATIONS:
            raise ValidationError(
                f"Unknown or disallowed operation '{self.name}'. "
                f"Allowed operations: {sorted(ALLOWLISTED_OPERATIONS)}"
            )

        # Validate parameters for specific operations
        self._validate_parameters()

    def _validate_parameters(self) -> None:
        """Enforce parameter schema rules per operation type."""
        if self.name == OperationName.RENAME_COLUMN.value:
            new_name = self.parameters.get("new_name")
            if not isinstance(new_name, str):
                raise ValidationError(
                    "Operation 'rename_column' requires parameter 'new_name' (str)."
                )
            if not self.columns or len(self.columns) != 1:
                raise ValidationError(
                    "Operation 'rename_column' requires exactly one target column in 'columns'."
                )

        elif self.name == OperationName.CAST_TYPE.value:
            if "target_type" not in self.parameters:
                raise ValidationError("Operation 'cast_type' requires parameter 'target_type'.")

        elif self.name == OperationName.FILL_MISSING.value:
            if "strategy" not in self.parameters:
                raise ValidationError("Operation 'fill_missing' requires parameter 'strategy'.")
            valid_strategies = {
                "constant",
                "mean",
                "median",
                "mode",
                "forward_fill",
                "backward_fill",
            }
            if self.parameters["strategy"] not in valid_strategies:
                raise ValidationError(
                    f"Invalid fill strategy '{self.parameters['strategy']}'. "
                    f"Valid strategies: {sorted(valid_strategies)}"
                )
            if self.parameters["strategy"] == "constant" and "value" not in self.parameters:
                raise ValidationError("Strategy 'constant' requires a 'value' parameter.")

        elif self.name == OperationName.FILTER_ROWS.value:
            if "condition" not in self.parameters or "operator" not in self.parameters:
                raise ValidationError(
                    "Operation 'filter_rows' requires 'condition' and 'operator' parameters."
                )

    def to_dict(self) -> dict[str, Any]:
        """Serialize operation to a clean JSON-compatible dictionary."""
        return {
            "id": self.id,
            "name": self.name,
            "version": self.version,
            "columns": list(self.columns),
            "parameters": dict(self.parameters),
            "enabled": self.enabled,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Operation:
        """Deserialize operation from a dictionary with strict validation."""
        if "name" not in data:
            raise ValidationError("Operation dictionary missing required key 'name'.")

        return cls(
            id=str(data.get("id", uuid.uuid4())),
            name=str(data["name"]),
            version=str(data.get("version", "1.0")),
            columns=[str(c) for c in data.get("columns", [])],
            parameters=dict(data.get("parameters", {})),
            enabled=bool(data.get("enabled", True)),
        )

    def with_enabled(self, enabled: bool) -> Operation:
        """Return a copy with updated enabled state."""
        return Operation(
            id=self.id,
            name=self.name,
            columns=list(self.columns),
            parameters=dict(self.parameters),
            version=self.version,
            enabled=enabled,
        )
