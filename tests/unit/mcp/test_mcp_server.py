"""Unit tests for the stdio Model Context Protocol (MCP) server."""

import json
from pathlib import Path

import pytest

from workbench.adapters.mcp.server import MCPServer


@pytest.fixture
def fixtures_dir() -> Path:
    return Path(__file__).parents[2] / "fixtures"


@pytest.fixture
def mcp_server() -> MCPServer:
    return MCPServer()


def test_mcp_initialize(mcp_server: MCPServer) -> None:
    req = {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}}
    res = mcp_server.handle_request(req)
    assert res is not None
    assert res["id"] == 1
    assert "result" in res
    assert res["result"]["serverInfo"]["name"] == "eatdata-mcp"
    assert "protocolVersion" in res["result"]


def test_mcp_notifications_ignored(mcp_server: MCPServer) -> None:
    notif = {"jsonrpc": "2.0", "method": "notifications/initialized"}
    res = mcp_server.handle_request(notif)
    assert res is None


def test_mcp_tools_list(mcp_server: MCPServer) -> None:
    req = {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}}
    res = mcp_server.handle_request(req)
    assert res is not None
    assert res["id"] == 2
    tools = res["result"]["tools"]
    tool_names = {t["name"] for t in tools}
    assert "profile_dataset" in tool_names
    assert "validate_pipeline" in tool_names
    assert "preview_transformation" in tool_names
    assert "list_templates" in tool_names


def test_mcp_tool_call_list_templates(mcp_server: MCPServer) -> None:
    req = {
        "jsonrpc": "2.0",
        "id": 3,
        "method": "tools/call",
        "params": {"name": "list_templates", "arguments": {}},
    }
    res = mcp_server.handle_request(req)
    assert res is not None
    assert "result" in res
    content = json.loads(res["result"]["content"][0]["text"])
    assert isinstance(content, list)
    assert len(content) >= 4


def test_mcp_tool_call_validate_pipeline(mcp_server: MCPServer) -> None:
    valid_pipe = {
        "id": "pipe-1",
        "name": "Test Pipeline",
        "version": "1.0",
        "steps": [{"name": "trim_whitespace", "columns": [], "parameters": {}}],
    }
    req = {
        "jsonrpc": "2.0",
        "id": 4,
        "method": "tools/call",
        "params": {
            "name": "validate_pipeline",
            "arguments": {"pipeline_json": json.dumps(valid_pipe)},
        },
    }
    res = mcp_server.handle_request(req)
    assert res is not None
    content = json.loads(res["result"]["content"][0]["text"])
    assert content["valid"] is True
    assert content["step_count"] == 1


def test_mcp_tool_call_profile_dataset(mcp_server: MCPServer, fixtures_dir: Path) -> None:
    csv_file = fixtures_dir / "clean_sample.csv"
    req = {
        "jsonrpc": "2.0",
        "id": 5,
        "method": "tools/call",
        "params": {"name": "profile_dataset", "arguments": {"file_path": str(csv_file)}},
    }
    res = mcp_server.handle_request(req)
    assert res is not None
    content = json.loads(res["result"]["content"][0]["text"])
    assert content["row_count"] > 0
    assert "columns" in content


def test_mcp_tool_call_preview(mcp_server: MCPServer, fixtures_dir: Path) -> None:
    csv_file = fixtures_dir / "clean_sample.csv"
    req = {
        "jsonrpc": "2.0",
        "id": 6,
        "method": "tools/call",
        "params": {
            "name": "preview_transformation",
            "arguments": {
                "file_path": str(csv_file),
                "operation_name": "trim_whitespace",
                "columns": ["full_name"],
            },
        },
    }
    res = mcp_server.handle_request(req)
    assert res is not None
    content = json.loads(res["result"]["content"][0]["text"])
    assert "before_rows" in content
    assert "after_rows" in content


def test_mcp_unknown_method(mcp_server: MCPServer) -> None:
    req = {"jsonrpc": "2.0", "id": 7, "method": "unknown_rpc_method"}
    res = mcp_server.handle_request(req)
    assert res is not None
    assert "error" in res
    assert res["error"]["code"] == -32601
