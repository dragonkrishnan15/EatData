"""Unit tests for AI providers (Mock, Ollama endpoint safety, Cloud)."""

import pytest

from workbench.adapters.ai.base import MockAIProvider
from workbench.adapters.ai.cloud_provider import CloudAIProvider
from workbench.adapters.ai.ollama_provider import OllamaProvider
from workbench.domain.errors import SecurityError, ValidationError


def test_mock_ai_provider() -> None:
    provider = MockAIProvider()
    assert provider.name == "mock"
    assert provider.is_local is True
    assert provider.health_check() is True

    payload = {
        "columns": [
            {"name": "full_name", "null_count": 0},
            {"name": "email", "null_count": 5},
        ]
    }
    recipe_str = provider.propose_recipe(payload, "trim whitespace and fill missing values")
    assert "trim_whitespace" in recipe_str
    assert "fill_missing" in recipe_str


def test_ollama_endpoint_security_validation() -> None:
    # 1. Loopback addresses should succeed
    p1 = OllamaProvider(endpoint="http://127.0.0.1:11434")
    assert p1.is_local is True
    p2 = OllamaProvider(endpoint="http://localhost:11434")
    assert p2.is_local is True

    # 2. Remote endpoints without allow_remote must raise SecurityError
    with pytest.raises(SecurityError, match="is remote"):
        OllamaProvider(endpoint="http://192.168.1.100:11434", allow_remote=False)

    with pytest.raises(SecurityError, match="is remote"):
        OllamaProvider(endpoint="https://external-ai-host.com:11434", allow_remote=False)

    # 3. Invalid schemes must raise SecurityError
    with pytest.raises(SecurityError, match="Invalid URL scheme"):
        OllamaProvider(endpoint="ftp://127.0.0.1:11434")


def test_cloud_provider_api_key_and_repr_privacy() -> None:
    # Missing API key triggers ValidationError on propose
    provider = CloudAIProvider(api_key=None)
    with pytest.raises(ValidationError, match="Missing API key"):
        provider.propose_recipe({}, "clean data")

    # With API key provided, verify __repr__ never leaks the key
    secret_key = "sk-super-secret-production-token-12345"
    provider_with_key = CloudAIProvider(api_key=secret_key)
    repr_str = repr(provider_with_key)
    assert secret_key not in repr_str
    assert "sk-" not in repr_str
