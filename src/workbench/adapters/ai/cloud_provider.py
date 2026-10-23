"""Cloud AI provider adapter (OpenAI / Gemini compatible).

Invariants:
- STRICT PRIVACY (Rule 8, 9): Only transmits allowlisted metadata packages.
- API keys are never written to logs, error representations, or database tables.
- Timeouts and connection failures raise ProviderUnavailableError.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from workbench.adapters.ai.base import AIProvider
from workbench.domain.errors import ProviderUnavailableError, ValidationError
from workbench.domain.operations import ALLOWLISTED_OPERATIONS

CLOUD_SYSTEM_PROMPT = f"""You are an offline data engineering assistant for EatData Workbench.
You receive dataset metadata (schema, column types, null counts, distinct counts).
You must propose a deterministic cleaning pipeline in valid JSON.
DO NOT output python code, scripts, or markdown explanations.
ONLY use the following allowed operation names:
{sorted(ALLOWLISTED_OPERATIONS)}

JSON format:
{{
  "name": "Cleaning Pipeline",
  "version": "1.0",
  "steps": [
    {{
      "name": "<operation_name>",
      "columns": ["<col1>"],
      "parameters": {{}}
    }}
  ]
}}
"""


class CloudAIProvider(AIProvider):
    """Generic cloud AI provider supporting OpenAI-compatible chat completion endpoints."""

    def __init__(
        self,
        name: str = "openai",
        api_key: str | None = None,
        endpoint: str = "https://api.openai.com/v1/chat/completions",
        model: str = "gpt-4o-mini",
        timeout_seconds: float = 30.0,
    ) -> None:
        self._name = name
        self.endpoint = endpoint
        self.model = model
        self.timeout = timeout_seconds
        # API key retrieval: explicit argument or environment variable
        self._api_key = api_key or os.environ.get("OPENAI_API_KEY") or os.environ.get("AI_API_KEY")

    @property
    def name(self) -> str:
        return self._name

    @property
    def is_local(self) -> bool:
        return False

    def health_check(self) -> bool:
        """Verify API key presence and endpoint validity."""
        return bool(self._api_key and self.endpoint.startswith("https://"))

    def propose_recipe(self, metadata_payload: dict[str, Any], prompt: str) -> str:
        if not self._api_key:
            raise ValidationError(
                f"Missing API key for cloud provider '{self.name}'. "
                "Set OPENAI_API_KEY environment variable or pass api_key."
            )

        meta_str = json.dumps(metadata_payload, indent=2)
        user_content = f"User Request: {prompt}\n\nDataset Metadata:\n{meta_str}"

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": CLOUD_SYSTEM_PROMPT},
                {"role": "user", "content": user_content},
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0.1,
        }

        req = urllib.request.Request(
            self.endpoint,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self._api_key}",
            },
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                choices = data.get("choices", [])
                if not choices:
                    raise ProviderUnavailableError("Cloud provider returned empty choices list.")
                return str(choices[0].get("message", {}).get("content", ""))
        except urllib.error.URLError as err:
            raise ProviderUnavailableError(
                f"Cloud provider connection failed ({self.name}): {err}"
            ) from err
        except Exception as err:
            raise ProviderUnavailableError(f"Cloud provider generation failed: {err}") from err

    def __repr__(self) -> str:
        # STRICT PRIVACY: NEVER expose API key in __repr__
        return f"CloudAIProvider(name='{self.name}', model='{self.model}')"
