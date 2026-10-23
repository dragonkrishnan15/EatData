"""Local Ollama AI provider adapter.

Invariants:
- STRICT PRIVACY: Executes on local machine endpoints (default: http://127.0.0.1:11434).
- Remote host endpoints are rejected unless explicitly authorized.
- Safe timeout handling and structured JSON recipe prompting.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from workbench.adapters.ai.base import AIProvider
from workbench.domain.errors import ProviderUnavailableError, SecurityError
from workbench.domain.operations import ALLOWLISTED_OPERATIONS

OLLAMA_SYSTEM_PROMPT = f"""You are an expert data cleaning assistant for EatData Workbench.
You receive a dataset metadata summary (column names, types, null counts, distinct counts).
You must propose a data cleaning pipeline in valid JSON.
DO NOT output any python code, scripts, or markdown prose.
ONLY use the following allowed operation names:
{sorted(ALLOWLISTED_OPERATIONS)}

JSON format required:
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


class OllamaProvider(AIProvider):
    """Local Ollama provider communicating with the local Ollama daemon."""

    def __init__(
        self,
        endpoint: str = "http://127.0.0.1:11434",
        model: str = "llama3:latest",
        timeout_seconds: float = 30.0,
        allow_remote: bool = False,
    ) -> None:
        self.endpoint = endpoint.rstrip("/")
        self.model = model
        self.timeout = timeout_seconds
        self.allow_remote = allow_remote
        self._validate_endpoint()

    def _validate_endpoint(self) -> None:
        """Enforce loopback safety rule unless remote access is explicitly flagged."""
        parsed = urllib.parse.urlparse(self.endpoint)
        if parsed.scheme not in ("http", "https"):
            raise SecurityError(
                f"Invalid URL scheme '{parsed.scheme}'. Ollama endpoint must use http or https."
            )
        host = parsed.hostname or ""
        if not self.allow_remote and host not in ("127.0.0.1", "localhost", "::1"):
            raise SecurityError(
                f"Security violation: Ollama endpoint host '{host}' is remote. "
                "Local-first workbench requires loopback (127.0.0.1) unless allow_remote is set."
            )

    @property
    def name(self) -> str:
        return "ollama"

    @property
    def is_local(self) -> bool:
        return True

    def health_check(self) -> bool:
        """Check if Ollama server is responding."""
        try:
            req = urllib.request.Request(f"{self.endpoint}/api/tags", method="GET")
            with urllib.request.urlopen(req, timeout=3.0) as resp:
                return resp.status == 200
        except Exception:
            return False

    def propose_recipe(self, metadata_payload: dict[str, Any], prompt: str) -> str:
        """Call local Ollama /api/generate endpoint to propose a cleaning recipe."""
        url = f"{self.endpoint}/api/generate"
        meta_str = json.dumps(metadata_payload, indent=2)
        user_message = f"User Request: {prompt}\n\nDataset Metadata:\n{meta_str}"

        payload = {
            "model": self.model,
            "system": OLLAMA_SYSTEM_PROMPT,
            "prompt": user_message,
            "format": "json",
            "stream": False,
        }

        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                return str(data.get("response", ""))
        except urllib.error.URLError as err:
            raise ProviderUnavailableError(
                f"Failed to communicate with local Ollama at '{self.endpoint}': {err}"
            ) from err
        except Exception as err:
            raise ProviderUnavailableError(f"Ollama generation failed: {err}") from err
