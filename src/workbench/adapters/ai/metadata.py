"""Privacy-preserving metadata package builder for AI proposal layer.

Invariants:
- STRICT PRIVACY (Rule 2, 6, 8): NEVER include raw data rows, cell values, or sensitive secrets.
- Metadata is allowlisted: schema, inferred types, null counts, distinct counts,
  and non-sensitive patterns.
- Column aliasing mode: optionally anonymizes column names before transmission, reversible locally.
- Payload preview: provides exact outgoing payload and SHA-256 hash for explicit user consent.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from typing import Any

from workbench.domain.errors import SecurityError
from workbench.domain.profile import DatasetProfile


@dataclass(frozen=True)
class ColumnMetadataSummary:
    """Safe allowlisted column summary."""

    name: str
    data_type: str
    null_count: int
    null_percentage: float
    distinct_count: int
    is_unique: bool
    pattern_summary: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class MetadataPackage:
    """A safe, inspectable metadata package for AI proposal generation."""

    schema_version: str
    row_count: int
    column_count: int
    columns: list[ColumnMetadataSummary]
    warnings: list[str]
    is_aliased: bool
    alias_mapping: dict[str, str] | None = None  # Original Name -> Alias

    @property
    def payload_dict(self) -> dict[str, Any]:
        """Construct the exact dictionary that will be transmitted."""
        return {
            "schema_version": self.schema_version,
            "row_count": self.row_count,
            "column_count": self.column_count,
            "columns": [c.to_dict() for c in self.columns],
            "warnings": self.warnings,
            "is_aliased": self.is_aliased,
        }

    @property
    def payload_json(self) -> str:
        """Formatted canonical JSON string of the outgoing payload."""
        return json.dumps(self.payload_dict, indent=2, sort_keys=True)

    @property
    def payload_hash(self) -> str:
        """Deterministic SHA-256 hash of the payload for consent verification."""
        canonical = json.dumps(self.payload_dict, sort_keys=True).encode("utf-8")
        return hashlib.sha256(canonical).hexdigest()


class MetadataPackageBuilder:
    """Constructs safe, privacy-preserving metadata packages from dataset profiles."""

    # Prohibited keys that MUST NEVER appear in an outgoing AI payload
    PROHIBITED_KEYS = frozenset(
        {
            "rows",
            "row",
            "values",
            "sample_values",
            "sample_categories",
            "data",
            "cells",
            "records",
            "filepath",
            "source_path",
        }
    )

    def build(self, profile: DatasetProfile, alias_columns: bool = False) -> MetadataPackage:
        """Build an allowlisted metadata package from a DatasetProfile."""
        alias_map: dict[str, str] = {}
        columns_summary: list[ColumnMetadataSummary] = []

        for idx, (col_name, col_prof) in enumerate(profile.columns.items()):
            effective_name = f"col_{idx + 1}" if alias_columns else col_name
            if alias_columns:
                alias_map[col_name] = effective_name

            # Inferred pattern summary (e.g. date format, general shape) without raw values
            pattern = None
            if col_prof.inferred_type.value == "date":
                pattern = "YYYY-MM-DD"
            elif col_prof.inferred_type.value == "datetime":
                pattern = "ISO-8601"

            summary = ColumnMetadataSummary(
                name=effective_name,
                data_type=col_prof.inferred_type.value,
                null_count=col_prof.null_count + col_prof.empty_string_count,
                null_percentage=col_prof.null_percentage,
                distinct_count=col_prof.distinct_count,
                is_unique=col_prof.is_unique,
                pattern_summary=pattern,
            )
            columns_summary.append(summary)

        package = MetadataPackage(
            schema_version="1.0",
            row_count=profile.row_count,
            column_count=profile.column_count,
            columns=columns_summary,
            warnings=list(profile.warnings),
            is_aliased=alias_columns,
            alias_mapping=alias_map if alias_columns else None,
        )

        # Verification gate: ensure no prohibited keys leaked
        self._verify_privacy_invariants(package.payload_dict)
        return package

    def _verify_privacy_invariants(self, payload: dict[str, Any]) -> None:
        """Verify that payload contains zero prohibited keys or raw row arrays."""

        def check_node(node: Any) -> None:
            if isinstance(node, dict):
                for k, v in node.items():
                    if k.lower() in self.PROHIBITED_KEYS:
                        raise SecurityError(
                            f"Privacy violation: prohibited key '{k}' found in AI payload."
                        )
                    check_node(v)
            elif isinstance(node, list):
                for item in node:
                    check_node(item)

        check_node(payload)

    def unalias_recipe_dict(
        self, recipe_dict: dict[str, Any], alias_mapping: dict[str, str]
    ) -> dict[str, Any]:
        """Reverse column aliasing in an AI-proposed recipe dictionary using the local mapping."""
        # Reverse map: alias (e.g. 'col_1') -> original name (e.g. 'customer_name')
        reverse_map = {alias: orig for orig, alias in alias_mapping.items()}

        unaliased = json.loads(json.dumps(recipe_dict))
        steps = unaliased.get("steps", [])

        for step in steps:
            # Unalias columns array
            cols = step.get("columns", [])
            step["columns"] = [reverse_map.get(c, c) for c in cols]

            # Unalias specific parameters (e.g. rename_column, split_column, combine_columns)
            params = step.get("parameters", {})
            if "column" in params and params["column"] in reverse_map:
                params["column"] = reverse_map[params["column"]]
            if "source_column" in params and params["source_column"] in reverse_map:
                params["source_column"] = reverse_map[params["source_column"]]
            if "source_columns" in params:
                params["source_columns"] = [reverse_map.get(c, c) for c in params["source_columns"]]

        return unaliased
