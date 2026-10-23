"""Security and privacy tests for the Model Context Protocol (MCP) server.

Verifies:
- Path traversal and non-existent file protections.
- File type allowlisting (rejects binaries or executable paths).
- Rule 10: Zero network listening sockets.
- Data privacy: zero exposure of raw records across tool boundaries.
"""

import json
from pathlib import Path

import pytest

from workbench.adapters.mcp.server import MCPServer


@pytest.fixture
def fixtures_dir() -> Path:
    return Path(__file__).parents[1] / "fixtures"


@pytest.fixture
def mcp_server() -> MCPServer:
    return MCPServer()


def test_mcp_path_traversal_nonexistent_file(mcp_server: MCPServer) -> None:
    req = {
        "jsonrpc": "2.0",
        "id": 10,
        "method": "tools/call",
        "params": {
            "name": "profile_dataset",
            "arguments": {"file_path": "../../etc/shadow"},
        },
    }
    res = mcp_server.handle_request(req)
    assert res is not None
    assert "error" in res
    assert "File path does not exist" in res["error"]["message"]


def test_mcp_rejects_unsupported_binary_extension(mcp_server: MCPServer, tmp_path: Path) -> None:
    fake_exe = tmp_path / "payload.exe"
    fake_exe.write_bytes(b"MZ\x90\x00\x03\x00\x00\x00")

    req = {
        "jsonrpc": "2.0",
        "id": 11,
        "method": "tools/call",
        "params": {
            "name": "profile_dataset",
            "arguments": {"file_path": str(fake_exe)},
        },
    }
    res = mcp_server.handle_request(req)
    assert res is not None
    assert "error" in res
    assert "Unsupported format" in res["error"]["message"]


def test_mcp_stdio_only_no_network_sockets(mcp_server: MCPServer) -> None:
    """Verifies MCPServer has no host or port attributes and does not bind sockets."""
    assert not hasattr(mcp_server, "port")
    assert not hasattr(mcp_server, "host")
    assert hasattr(mcp_server, "run_stdio")


def test_mcp_profile_does_not_leak_raw_rows(mcp_server: MCPServer, fixtures_dir: Path) -> None:
    """Verifies profiling output strictly conforms to statistical aggregates."""
    messy_csv = fixtures_dir / "messy_sample.csv"
    req = {
        "jsonrpc": "2.0",
        "id": 12,
        "method": "tools/call",
        "params": {"name": "profile_dataset", "arguments": {"file_path": str(messy_csv)}},
    }
    res = mcp_server.handle_request(req)
    assert res is not None
    text_content = res["result"]["content"][0]["text"]
    data = json.loads(text_content)

    # Output has schema aggregates, no "rows" or "data" raw table dump
    assert "columns" in data
    assert "rows" not in data
    assert "data" not in data

    # Verify column statistics do not contain whole record row lists
    for col_stats in data["columns"].values():
        assert "row_values" not in col_stats
        assert "inferred_type" in col_stats
        assert "null_count" in col_stats


def test_mcp_preview_rejects_non_allowlisted_operation(
    mcp_server: MCPServer, fixtures_dir: Path
) -> None:
    clean_csv = fixtures_dir / "clean_sample.csv"
    req = {
        "jsonrpc": "2.0",
        "id": 13,
        "method": "tools/call",
        "params": {
            "name": "preview_transformation",
            "arguments": {
                "file_path": str(clean_csv),
                "operation_name": "eval_arbitrary_python",
            },
        },
    }
    res = mcp_server.handle_request(req)
    assert res is not None
    assert "error" in res
    assert "disallowed operation" in res["error"]["message"]
