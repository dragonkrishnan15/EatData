"""AI adapter package for optional recipe proposals."""

from workbench.adapters.ai.base import AIProvider, ConsentGate, MockAIProvider
from workbench.adapters.ai.cloud_provider import CloudAIProvider
from workbench.adapters.ai.metadata import MetadataPackage, MetadataPackageBuilder
from workbench.adapters.ai.ollama_provider import OllamaProvider
from workbench.adapters.ai.recipe_schema import RecipeValidator
from workbench.adapters.ai.router import AIRouter

__all__ = [
    "AIProvider",
    "AIRouter",
    "CloudAIProvider",
    "ConsentGate",
    "MetadataPackage",
    "MetadataPackageBuilder",
    "MockAIProvider",
    "OllamaProvider",
    "RecipeValidator",
]
