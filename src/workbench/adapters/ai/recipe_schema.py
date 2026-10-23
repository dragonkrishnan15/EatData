"""Strict recipe schema and validator for AI proposals.

Invariants:
- All operations in the proposed recipe MUST belong to the strict ALLOWLISTED_OPERATIONS vocabulary.
- Rejects arbitrary code execution attempts, eval, scripts, unknown keys, and malicious payloads.
- Validates parameter schemas, ranges, and types for every step.
- Converts approved recipes into standard, reproducible Pipeline domain objects.
"""

from __future__ import annotations

import json
import re
from typing import Any

from workbench.domain.errors import InvalidRecipeError
from workbench.domain.operations import ALLOWLISTED_OPERATIONS, Operation
from workbench.domain.pipeline import Pipeline

FORBIDDEN_CODE_PATTERNS = [
    re.compile(r"\b(eval|exec|compile|__import__|open|input)\b", re.IGNORECASE),
    re.compile(r"\b(os\.|sys\.|subprocess\.|shutil\.|socket\.)", re.IGNORECASE),
    re.compile(r"\b(import\s+|from\s+\w+\s+import)", re.IGNORECASE),
    re.compile(r"\b(def\s+\w+|class\s+\w+|lambda\b)", re.IGNORECASE),
]


class RecipeValidator:
    """Validates and parses proposed transformation recipes from AI providers."""

    ALLOWED_ROOT_KEYS = frozenset({"name", "version", "description", "steps"})
    ALLOWED_STEP_KEYS = frozenset({"name", "columns", "parameters", "enabled", "id"})

    def parse_and_validate(self, raw_recipe: str | dict[str, Any]) -> Pipeline:
        """Parse, validate, and convert a raw AI response into an executable Pipeline."""
        # 1. Parse JSON if string
        recipe_dict: dict[str, Any]
        if isinstance(raw_recipe, str):
            # Strip markdown code blocks if the model wrapped it in ```json ... ```
            cleaned = self._strip_markdown_code_fences(raw_recipe)
            try:
                recipe_dict = json.loads(cleaned)
            except Exception as err:
                raise InvalidRecipeError(f"Proposed recipe is not valid JSON: {err}") from err
        elif isinstance(raw_recipe, dict):
            recipe_dict = raw_recipe
        else:
            raise InvalidRecipeError(
                f"Recipe must be JSON string or dict, got: {type(raw_recipe).__name__}"
            )

        # 2. Check for code injection patterns across all text values
        self._check_for_executable_code(recipe_dict)

        # 3. Validate root structure
        if not isinstance(recipe_dict, dict):
            raise InvalidRecipeError("Recipe root must be a JSON object.")

        unknown_root = set(recipe_dict.keys()) - self.ALLOWED_ROOT_KEYS
        if unknown_root:
            raise InvalidRecipeError(f"Recipe contains unauthorized root keys: {unknown_root}")

        steps_data = recipe_dict.get("steps")
        if not isinstance(steps_data, list):
            raise InvalidRecipeError("Recipe 'steps' must be a list of transformation operations.")

        # 4. Validate each individual operation step
        operations: list[Operation] = []
        for idx, step in enumerate(steps_data):
            if not isinstance(step, dict):
                raise InvalidRecipeError(f"Step {idx} must be a JSON object.")

            unknown_step_keys = set(step.keys()) - self.ALLOWED_STEP_KEYS
            if unknown_step_keys:
                raise InvalidRecipeError(
                    f"Step {idx} contains unauthorized keys: {unknown_step_keys}"
                )

            op_name = step.get("name")
            if not op_name:
                raise InvalidRecipeError(f"Step {idx} is missing required 'name' field.")

            if op_name not in ALLOWLISTED_OPERATIONS:
                raise InvalidRecipeError(
                    f"Step {idx} uses disallowed operation '{op_name}'. "
                    f"Allowed operations: {sorted(ALLOWLISTED_OPERATIONS)}"
                )

            cols = step.get("columns", [])
            if not isinstance(cols, list):
                raise InvalidRecipeError(f"Step {idx} 'columns' must be a list of strings.")

            params = step.get("parameters", {})
            if not isinstance(params, dict):
                raise InvalidRecipeError(f"Step {idx} 'parameters' must be a dictionary.")

            # Create Operation (triggers domain-level parameter validation)
            try:
                op = Operation(
                    name=op_name,
                    columns=[str(c) for c in cols],
                    parameters=params,
                    enabled=bool(step.get("enabled", True)),
                )
            except Exception as err:
                raise InvalidRecipeError(f"Step {idx} parameter validation failed: {err}") from err

            operations.append(op)

        return Pipeline(
            name=str(recipe_dict.get("name", "AI Proposed Pipeline")),
            version=str(recipe_dict.get("version", "1.0")),
            steps=operations,
        )

    def _strip_markdown_code_fences(self, text: str) -> str:
        text = text.strip()
        if text.startswith("```"):
            lines = text.splitlines()
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            return "\n".join(lines).strip()
        return text

    def _check_for_executable_code(self, obj: Any) -> None:
        """Recursively scan strings in the recipe for Python code or shell patterns."""
        if isinstance(obj, str):
            for pattern in FORBIDDEN_CODE_PATTERNS:
                if pattern.search(obj):
                    raise InvalidRecipeError(
                        f"Security violation: dangerous code pattern detected in recipe: '{obj}'"
                    )
        elif isinstance(obj, dict):
            for k, v in obj.items():
                self._check_for_executable_code(k)
                self._check_for_executable_code(v)
        elif isinstance(obj, list):
            for item in obj:
                self._check_for_executable_code(item)
