"""AI Provider Router and orchestration layer.

Invariants:
- STRICT PRIVACY (Rule 8, 9, 10): External calls strictly gated by ConsentGate.
- Reverses column aliasing locally before recipe validation.
- All proposed recipes pass strict validation against ALLOWLISTED_OPERATIONS.
"""

from __future__ import annotations

import json

from workbench.adapters.ai.base import AIProvider, ConsentGate, MockAIProvider
from workbench.adapters.ai.metadata import MetadataPackage, MetadataPackageBuilder
from workbench.adapters.ai.recipe_schema import RecipeValidator
from workbench.domain.errors import ValidationError
from workbench.domain.pipeline import Pipeline


class AIRouter:
    """Orchestrates AI providers, consent gates, and recipe translation."""

    def __init__(self, consent_gate: ConsentGate | None = None) -> None:
        self.consent_gate = consent_gate or ConsentGate()
        self._providers: dict[str, AIProvider] = {
            "mock": MockAIProvider(),
        }
        self.metadata_builder = MetadataPackageBuilder()
        self.recipe_validator = RecipeValidator()

    def register_provider(self, provider: AIProvider) -> None:
        """Register an AI provider instance."""
        self._providers[provider.name] = provider

    def get_provider(self, name: str) -> AIProvider:
        """Retrieve a provider by name."""
        if name not in self._providers:
            available = sorted(self._providers.keys())
            raise ValidationError(f"Unknown AI provider '{name}'. Available providers: {available}")
        return self._providers[name]

    def list_providers(self) -> list[dict[str, str | bool]]:
        """List all registered providers with locality and status."""
        result: list[dict[str, str | bool]] = []
        for name, p in self._providers.items():
            result.append(
                {
                    "name": name,
                    "is_local": p.is_local,
                    "available": p.health_check(),
                }
            )
        return result

    def request_recipe(
        self,
        provider_name: str,
        package: MetadataPackage,
        prompt: str,
        explicit_consent: bool = False,
    ) -> Pipeline:
        """Request and validate a recipe proposal through the consent gate."""
        provider = self.get_provider(provider_name)

        # 1. Check and record consent
        if explicit_consent:
            self.consent_gate.grant_consent(provider_name, package.payload_hash)
        else:
            self.consent_gate.verify_consent(provider_name, package.payload_hash)

        # 2. Transmit metadata payload to provider
        raw_response = provider.propose_recipe(package.payload_dict, prompt)

        # 3. If column aliasing was used, unalias the recipe before validation
        if package.is_aliased and package.alias_mapping:
            cleaned = self.recipe_validator._strip_markdown_code_fences(raw_response)
            try:
                recipe_dict = json.loads(cleaned)
                unaliased_dict = self.metadata_builder.unalias_recipe_dict(
                    recipe_dict, package.alias_mapping
                )
                return self.recipe_validator.parse_and_validate(unaliased_dict)
            except Exception as err:
                raise ValidationError(f"Failed to unalias AI recipe: {err}") from err

        # 4. Parse and validate recipe into a Pipeline
        return self.recipe_validator.parse_and_validate(raw_response)
