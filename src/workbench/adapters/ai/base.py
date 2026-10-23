"""Base AI provider interface, consent gate, and offline mock provider.

Invariants:
- STRICT PRIVACY (Rule 8, 9, 10): External AI transmissions require explicit per-payload consent.
- Providers only receive allowlisted metadata packages (never raw rows).
- Missing consent immediately raises ConsentRequiredError.
"""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from typing import Any

from workbench.domain.errors import ConsentRequiredError


class AIProvider(ABC):
    """Abstract interface for AI recipe proposal providers."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Provider identifier (e.g. 'mock', 'ollama', 'openai', 'gemini')."""

    @property
    @abstractmethod
    def is_local(self) -> bool:
        """True if execution is 100% on the local machine (e.g. Ollama)."""

    @abstractmethod
    def health_check(self) -> bool:
        """Check if provider endpoint is reachable and operational."""

    @abstractmethod
    def propose_recipe(self, metadata_payload: dict[str, Any], prompt: str) -> str:
        """Generate a proposed transformation recipe JSON string."""


class ConsentGate:
    """Manages and enforces explicit user consent for metadata transmissions."""

    def __init__(self) -> None:
        # Map of (provider_name, payload_hash) -> bool
        self._consents: set[tuple[str, str]] = set()

    def grant_consent(self, provider_name: str, payload_hash: str) -> None:
        """Record explicit user approval to transmit the given payload to the provider."""
        self._consents.add((provider_name, payload_hash))

    def has_consent(self, provider_name: str, payload_hash: str) -> bool:
        """Check if user consent was granted for this exact provider and payload."""
        return (provider_name, payload_hash) in self._consents

    def verify_consent(self, provider_name: str, payload_hash: str) -> None:
        """Raise ConsentRequiredError if explicit consent has not been granted."""
        if not self.has_consent(provider_name, payload_hash):
            raise ConsentRequiredError(
                f"User consent required to send metadata payload to AI provider '{provider_name}'. "
                f"Payload hash: {payload_hash[:12]}..."
            )

    def revoke_all(self) -> None:
        """Clear all active consents."""
        self._consents.clear()


class MockAIProvider(AIProvider):
    """Deterministic offline mock provider for testing and air-gapped demo runs."""

    def __init__(self, name: str = "mock") -> None:
        self._name = name

    @property
    def name(self) -> str:
        return self._name

    @property
    def is_local(self) -> bool:
        return True

    def health_check(self) -> bool:
        return True

    def propose_recipe(self, metadata_payload: dict[str, Any], prompt: str) -> str:
        """Generate a deterministic recipe JSON matching user prompt intent."""
        cols = [c["name"] for c in metadata_payload.get("columns", [])]
        p_lower = prompt.lower()

        steps: list[dict[str, Any]] = []

        # Standard cleaning steps based on keywords
        if "whitespace" in p_lower or "trim" in p_lower or "clean" in p_lower:
            steps.append(
                {
                    "name": "trim_whitespace",
                    "columns": cols,
                    "parameters": {},
                }
            )

        if "duplicate" in p_lower or "dedup" in p_lower or "clean" in p_lower:
            steps.append(
                {
                    "name": "drop_duplicates",
                    "columns": [],
                    "parameters": {},
                }
            )

        if "header" in p_lower or "normalize" in p_lower:
            steps.append(
                {
                    "name": "normalize_headers",
                    "columns": [],
                    "parameters": {"case": "snake"},
                }
            )

        if "missing" in p_lower or "fill" in p_lower:
            # Find a column with missing values
            cols_meta = metadata_payload.get("columns", [])
            missing_cols = [c["name"] for c in cols_meta if c.get("null_count", 0) > 0]
            target_col = missing_cols[0] if missing_cols else (cols[0] if cols else "col")
            steps.append(
                {
                    "name": "fill_missing",
                    "columns": [target_col],
                    "parameters": {"strategy": "constant", "value": "Unknown"},
                }
            )

        # Default fallback if prompt is generic
        if not steps:
            steps.append(
                {
                    "name": "trim_whitespace",
                    "columns": cols,
                    "parameters": {},
                }
            )

        recipe = {
            "name": f"Mock Recipe for: {prompt[:30]}",
            "version": "1.0",
            "description": "Automatically generated offline recipe based on metadata analysis.",
            "steps": steps,
        }
        return json.dumps(recipe, indent=2)
