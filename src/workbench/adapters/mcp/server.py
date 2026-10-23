"""Model Context Protocol (MCP) server over local stdio transport.

Invariants:
- STRICT PRIVACY (Rule 10, Threat Model): ZERO listening network sockets.
- Strictly communicates via stdio (stdin/stdout) parent-child JSON-RPC 2.0 messages.
- Exposes read-only profiling, pipeline validation, and transformation prospective previews.
- Strictly validates filesystem paths to prevent path traversal outside existing regular files.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from workbench.adapters.importers.csv_importer import CsvImporter
from workbench.adapters.importers.json_importer import JsonImporter
from workbench.domain.errors import ValidationError
from workbench.domain.operations import Operation
from workbench.domain.pipeline import Pipeline
from workbench.engine.preview import PreviewEngine
from workbench.engine.profiler import Profiler
from workbench.engine.registry import TransformationRegistry
from workbench.templates.catalog import TemplateCatalog

SERVER_NAME = "eatdata-mcp"
SERVER_VERSION = "1.0.0"


class MCPServer:
    """Local JSON-RPC 2.0 Model Context Protocol server over stdio."""

    def __init__(self) -> None:
        self.profiler = Profiler()
        self.preview_engine = PreviewEngine(TransformationRegistry())
        self.catalog = TemplateCatalog()

    def run_stdio(self) -> None:
        """Read JSON-RPC requests line-by-line from stdin and write responses to stdout."""
        for line in sys.stdin:
            line = line.strip()
            if not line:
                continue
            try:
                request = json.loads(line)
                response = self.handle_request(request)
                if response is not None:
                    sys.stdout.write(json.dumps(response) + "\n")
                    sys.stdout.flush()
            except Exception as err:
                err_resp = {
                    "jsonrpc": "2.0",
                    "id": None,
                    "error": {"code": -32700, "message": f"Parse error: {err}"},
                }
                sys.stdout.write(json.dumps(err_resp) + "\n")
                sys.stdout.flush()

    def handle_request(self, request: dict[str, Any]) -> dict[str, Any] | None:
        """Route JSON-RPC request to appropriate MCP handler."""
        req_id = request.get("id")
        method = request.get("method", "")
        params = request.get("params", {})

        if method == "initialize":
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {"tools": {}},
                    "serverInfo": {"name": SERVER_NAME, "version": SERVER_VERSION},
                },
            }

        if method == "tools/list":
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {"tools": self._get_tool_definitions()},
            }

        if method == "tools/call":
            tool_name = params.get("name")
            arguments = params.get("arguments", {})
            try:
                res = self._execute_tool(tool_name, arguments)
                return {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {"content": [{"type": "text", "text": json.dumps(res, indent=2)}]},
                }
            except Exception as err:
                return {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "error": {"code": -32603, "message": str(err)},
                }

        # Notification or unknown method
        if req_id is not None:
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {"code": -32601, "message": f"Method '{method}' not found."},
            }
        return None

    def _get_tool_definitions(self) -> list[dict[str, Any]]:
        return [
            {
                "name": "profile_dataset",
                "description": (
                    "Generate privacy-safe schema and statistical quality profile for a "
                    "local CSV/JSON file."
                ),
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "file_path": {
                            "type": "string",
                            "description": "Local path to dataset file",
                        }
                    },
                    "required": ["file_path"],
                },
            },
            {
                "name": "validate_pipeline",
                "description": (
                    "Validate a transformation pipeline JSON specification against "
                    "allowlisted operations."
                ),
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "pipeline_json": {
                            "type": "string",
                            "description": "JSON string of pipeline definition",
                        }
                    },
                    "required": ["pipeline_json"],
                },
            },
            {
                "name": "preview_transformation",
                "description": (
                    "Compute prospective before-and-after slices and cell diff coordinates "
                    "for an operation."
                ),
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "file_path": {"type": "string", "description": "Path to dataset file"},
                        "operation_name": {
                            "type": "string",
                            "description": "Allowlisted operation name",
                        },
                        "columns": {"type": "array", "items": {"type": "string"}},
                        "parameters": {"type": "object"},
                    },
                    "required": ["file_path", "operation_name"],
                },
            },
            {
                "name": "list_templates",
                "description": "List available curated industry cleaning templates.",
                "inputSchema": {"type": "object"},
            },
        ]

    def _execute_tool(self, name: str, args: dict[str, Any]) -> Any:
        if name == "profile_dataset":
            path_str = args.get("file_path", "")
            p = self._validate_path(path_str)
            dataset = self._load_file(p)
            return self.profiler.profile(dataset).to_dict()

        if name == "validate_pipeline":
            json_str = args.get("pipeline_json", "")
            pipe = Pipeline.from_json(json_str)
            return {"valid": True, "name": pipe.name, "step_count": len(pipe.steps)}

        if name == "preview_transformation":
            p = self._validate_path(args.get("file_path", ""))
            dataset = self._load_file(p)
            op = Operation(
                name=args.get("operation_name", ""),
                columns=args.get("columns", []),
                parameters=args.get("parameters", {}),
            )
            preview = self.preview_engine.preview_operation(dataset, op)
            return preview.to_dict()

        if name == "list_templates":
            return [t.to_dict() for t in self.catalog.list_templates()]

        raise ValidationError(f"Unknown MCP tool: '{name}'")

    def _validate_path(self, path_str: str) -> Path:
        if not path_str:
            raise ValidationError("File path argument is required.")
        p = Path(path_str).resolve()
        if not p.exists() or not p.is_file():
            raise ValidationError(f"File path does not exist or is not a regular file: {path_str}")
        return p

    def _load_file(self, path: Path):
        ext = path.suffix.lower()
        if ext in (".csv", ".tsv", ".txt"):
            return CsvImporter().import_file(path).dataset
        elif ext in (".json", ".ndjson", ".jsonl"):
            return JsonImporter().import_file(path).dataset
        raise ValidationError(f"Unsupported format: '{ext}'")
