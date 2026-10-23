"""Pipeline domain model representing an ordered sequence of operations.

Invariants:
- Pipelines are versioned and fully reproducible.
- Steps can be enabled, disabled, reordered, added, and removed.
- Validated against datasets before execution to catch missing columns early.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from typing import Any

from workbench.domain.dataset import Dataset
from workbench.domain.errors import ValidationError
from workbench.domain.operations import Operation


@dataclass(frozen=True)
class Pipeline:
    """An ordered, reproducible sequence of transformation operations."""

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = "Cleaning Pipeline"
    version: str = "1.0"
    steps: list[Operation] = field(default_factory=list)

    def add_step(self, operation: Operation) -> Pipeline:
        """Return a new Pipeline with the operation appended."""
        new_steps = list(self.steps) + [operation]
        return Pipeline(id=self.id, name=self.name, version=self.version, steps=new_steps)

    def remove_step(self, step_id: str) -> Pipeline:
        """Return a new Pipeline with the specified operation removed."""
        new_steps = [s for s in self.steps if s.id != step_id]
        if len(new_steps) == len(self.steps):
            raise ValidationError(f"Step with id '{step_id}' not found in pipeline.")
        return Pipeline(id=self.id, name=self.name, version=self.version, steps=new_steps)

    def reorder_step(self, from_index: int, to_index: int) -> Pipeline:
        """Return a new Pipeline with the step at from_index moved to to_index."""
        if not (0 <= from_index < len(self.steps)) or not (0 <= to_index < len(self.steps)):
            max_idx = len(self.steps) - 1
            raise ValidationError(
                f"Reorder indices ({from_index} -> {to_index}) out of range (0..{max_idx})."
            )
        new_steps = list(self.steps)
        item = new_steps.pop(from_index)
        new_steps.insert(to_index, item)
        return Pipeline(id=self.id, name=self.name, version=self.version, steps=new_steps)

    def toggle_step(self, step_id: str, enabled: bool) -> Pipeline:
        """Return a new Pipeline with the specified operation enabled or disabled."""
        found = False
        new_steps = []
        for s in self.steps:
            if s.id == step_id:
                new_steps.append(s.with_enabled(enabled))
                found = True
            else:
                new_steps.append(s)
        if not found:
            raise ValidationError(f"Step with id '{step_id}' not found in pipeline.")
        return Pipeline(id=self.id, name=self.name, version=self.version, steps=new_steps)

    def validate_against_dataset(self, dataset: Dataset) -> list[str]:
        """Verify that all referenced columns exist in the dataset."""
        warnings: list[str] = []
        known_cols = set(dataset.column_names)

        for step in self.steps:
            if not step.enabled:
                continue
            for col in step.columns:
                if col not in known_cols:
                    warnings.append(
                        f"Step '{step.name}' references column '{col}' missing from dataset."
                    )
            # Track column renames to maintain column graph awareness
            if step.name == "rename_column" and step.columns:
                src_col = step.columns[0]
                new_name = step.parameters.get("new_name")
                if src_col in known_cols and new_name:
                    known_cols.remove(src_col)
                    known_cols.add(new_name)

        return warnings

    def to_dict(self) -> dict[str, Any]:
        """Serialize pipeline to a dictionary."""
        return {
            "id": self.id,
            "name": self.name,
            "version": self.version,
            "steps": [s.to_dict() for s in self.steps],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Pipeline:
        """Deserialize pipeline from a dictionary."""
        steps_data = data.get("steps", [])
        steps = [Operation.from_dict(s) for s in steps_data]
        return cls(
            id=str(data.get("id", uuid.uuid4())),
            name=str(data.get("name", "Cleaning Pipeline")),
            version=str(data.get("version", "1.0")),
            steps=steps,
        )

    def to_json(self, indent: int = 2) -> str:
        """Serialize pipeline to formatted JSON."""
        return json.dumps(self.to_dict(), indent=indent)

    @classmethod
    def from_json(cls, json_str: str) -> Pipeline:
        """Deserialize pipeline from JSON string."""
        try:
            data = json.loads(json_str)
        except Exception as err:
            raise ValidationError(f"Failed to parse pipeline JSON: {err}") from err
        if not isinstance(data, dict):
            raise ValidationError("Pipeline JSON root must be an object.")
        return cls.from_dict(data)
