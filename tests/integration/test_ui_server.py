"""Integration tests for the local desktop UI loopback server."""

import json
import threading
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Generator
from pathlib import Path

import pytest

from workbench.domain.errors import SecurityError
from workbench.ui.server import WorkbenchServer


@pytest.fixture(scope="module")
def ui_server() -> Generator[str, None, None]:
    """Start WorkbenchServer on an ephemeral port on 127.0.0.1 for testing."""
    server = WorkbenchServer(host="127.0.0.1", port=0)
    server.start()
    port = server.port
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()

    base_url = f"http://127.0.0.1:{port}"
    yield base_url

    server.shutdown()


def test_loopback_security_enforcement() -> None:
    """Invariant Rule 10: Binding to remote interfaces like 0.0.0.0 is strictly prohibited."""
    with pytest.raises(SecurityError, match="must strictly bind to loopback"):
        WorkbenchServer(host="0.0.0.0", port=8080)

    with pytest.raises(SecurityError, match="must strictly bind to loopback"):
        WorkbenchServer(host="192.168.1.50", port=8080)


def test_ui_health_endpoint(ui_server: str) -> None:
    req = urllib.request.Request(f"{ui_server}/api/health")
    with urllib.request.urlopen(req) as resp:
        assert resp.status == 200
        data = json.loads(resp.read().decode("utf-8"))
        assert data["status"] == "ok"
        assert "EatData" in data["app"]


def test_ui_serves_html(ui_server: str) -> None:
    req = urllib.request.Request(f"{ui_server}/")
    with urllib.request.urlopen(req) as resp:
        assert resp.status == 200
        content = resp.read().decode("utf-8")
        assert "<!DOCTYPE html>" in content
        assert "EatData" in content


def test_api_import_and_profile(ui_server: str) -> None:
    fixture_path = str(Path("tests/fixtures/clean_sample.csv").resolve())
    payload = json.dumps({"filepath": fixture_path}).encode("utf-8")
    req = urllib.request.Request(
        f"{ui_server}/api/import",
        data=payload,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req) as resp:
        assert resp.status == 200
        data = json.loads(resp.read().decode("utf-8"))
        assert "dataset" in data
        assert "profile" in data
        assert data["dataset"]["name"] == "clean_sample"
        assert len(data["dataset"]["rows"]) == 5
        assert data["profile"]["row_count"] == 5


def test_api_transform_and_preview(ui_server: str) -> None:
    ds_payload = {
        "id": "test-id",
        "name": "sample",
        "columns": [
            {"name": "name", "data_type": "string"},
            {"name": "val", "data_type": "string"},
        ],
        "rows": [["  alice  ", "10"], ["bob", "  20  "]],
    }

    # Test preview
    op_payload = {"name": "trim_whitespace", "columns": ["name", "val"], "parameters": {}}
    prev_req = urllib.request.Request(
        f"{ui_server}/api/preview",
        data=json.dumps({"dataset": ds_payload, "operation": op_payload}).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(prev_req) as prev_resp:
        assert prev_resp.status == 200
        prev_data = json.loads(prev_resp.read().decode("utf-8"))
        assert len(prev_data["modified_cells"]) > 0

    # Test transform
    pipe_payload = {
        "id": "pipe-1",
        "name": "Clean Pipe",
        "version": "1.0",
        "steps": [op_payload],
    }
    trans_req = urllib.request.Request(
        f"{ui_server}/api/transform",
        data=json.dumps({"dataset": ds_payload, "pipeline": pipe_payload}).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(trans_req) as trans_resp:
        assert trans_resp.status == 200
        trans_data = json.loads(trans_resp.read().decode("utf-8"))
        assert trans_data["dataset"]["rows"][0][0] == "alice"


def test_api_chart(ui_server: str) -> None:
    ds_payload = {
        "id": "test-id",
        "name": "sample",
        "columns": [
            {"name": "cat", "data_type": "string"},
            {"name": "num", "data_type": "integer"},
        ],
        "rows": [["A", 10], ["B", 20], ["A", 30]],
    }
    chart_payload = {
        "dataset": ds_payload,
        "spec": {
            "chart_type": "bar",
            "title": "Bar Chart",
            "x_column": "cat",
            "aggregation": "count",
        },
    }
    req = urllib.request.Request(
        f"{ui_server}/api/chart",
        data=json.dumps(chart_payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req) as resp:
        assert resp.status == 200
        data = json.loads(resp.read().decode("utf-8"))
        assert data["type"] == "bar"
        assert "A" in data["labels"]


def test_api_export(ui_server: str, tmp_path: Path) -> None:
    out_file = str(tmp_path / "exported_test.csv")
    ds_payload = {
        "id": "test-id",
        "name": "sample",
        "columns": [{"name": "col1", "data_type": "string"}],
        "rows": [["val1"], ["val2"]],
    }
    export_payload = {
        "dataset": ds_payload,
        "filename": out_file,
        "overwrite": True,
    }
    req = urllib.request.Request(
        f"{ui_server}/api/export",
        data=json.dumps(export_payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req) as resp:
        assert resp.status == 200
        data = json.loads(resp.read().decode("utf-8"))
        assert data["status"] == "ok"
        assert data["rows_exported"] == 2
        assert Path(out_file).exists()


def test_api_ai_preview_and_propose(ui_server: str) -> None:
    ds_payload = {
        "id": "ai-test-id",
        "name": "sample",
        "columns": [
            {"name": "full_name", "data_type": "string"},
            {"name": "email", "data_type": "string"},
        ],
        "rows": [["  alice smith  ", "alice@test.com"], ["bob jones", ""]],
    }

    # 1. Preview payload
    prev_req = urllib.request.Request(
        f"{ui_server}/api/ai/preview-payload",
        data=json.dumps({"dataset": ds_payload, "alias_columns": True}).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(prev_req) as resp:
        assert resp.status == 200
        data = json.loads(resp.read().decode("utf-8"))
        assert "hash" in data
        assert "payload" in data
        assert data["payload"]["is_aliased"] is True
        assert data["payload"]["columns"][0]["name"] == "col_1"

    # 2. Propose recipe
    prop_req = urllib.request.Request(
        f"{ui_server}/api/ai/propose",
        data=json.dumps(
            {
                "dataset": ds_payload,
                "prompt": "trim whitespace",
                "provider": "mock",
                "consent": True,
                "alias_columns": True,
            }
        ).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(prop_req) as resp:
        assert resp.status == 200
        data = json.loads(resp.read().decode("utf-8"))
        assert "pipeline" in data
        assert len(data["pipeline"]["steps"]) > 0
        # Columns in proposed recipe should be unaliased back to original names!
        assert "full_name" in data["pipeline"]["steps"][0]["columns"]


def test_api_import_excel(ui_server: str, tmp_path: Path) -> None:
    from tests.unit.importers.test_excel_importer import create_minimal_xlsx

    sample_data = {
        "Sheet1": [["id", "city", "rating"], [1, "San Francisco", 4.8], [2, "Tokyo", 4.9]]
    }
    file_path = tmp_path / "cities.xlsx"
    file_path.write_bytes(create_minimal_xlsx(sample_data))

    payload = json.dumps({"filepath": str(file_path)}).encode("utf-8")
    req = urllib.request.Request(
        f"{ui_server}/api/import",
        data=payload,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req) as resp:
        assert resp.status == 200
        data = json.loads(resp.read().decode("utf-8"))
        assert data["dataset"]["name"] == "cities"
        assert len(data["dataset"]["columns"]) == 3
        assert len(data["dataset"]["rows"]) == 2


def test_api_pipeline_persistence(ui_server: str) -> None:
    # 1. Save pipeline
    pipe_payload = {
        "pipeline": {
            "id": "test-pipe-101",
            "name": "Integration Clean Pipeline",
            "version": "1.0",
            "steps": [
                {
                    "name": "trim_whitespace",
                    "columns": ["col_1"],
                    "parameters": {},
                    "enabled": True,
                }
            ],
        },
        "description": "Integration test pipeline",
    }
    save_req = urllib.request.Request(
        f"{ui_server}/api/pipelines/save",
        data=json.dumps(pipe_payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(save_req) as resp:
        assert resp.status == 200
        data = json.loads(resp.read().decode("utf-8"))
        assert data["status"] == "saved"
        assert data["id"] == "test-pipe-101"

    # 2. List pipelines
    list_req = urllib.request.Request(f"{ui_server}/api/pipelines")
    with urllib.request.urlopen(list_req) as resp:
        assert resp.status == 200
        data = json.loads(resp.read().decode("utf-8"))
        assert "pipelines" in data
        assert any(p["id"] == "test-pipe-101" for p in data["pipelines"])

    # 3. Load pipeline
    load_req = urllib.request.Request(
        f"{ui_server}/api/pipelines/load",
        data=json.dumps({"id": "test-pipe-101"}).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(load_req) as resp:
        assert resp.status == 200
        data = json.loads(resp.read().decode("utf-8"))
        assert data["pipeline"]["name"] == "Integration Clean Pipeline"
        assert len(data["pipeline"]["steps"]) == 1

    # 4. Delete pipeline
    del_req = urllib.request.Request(
        f"{ui_server}/api/pipelines/delete",
        data=json.dumps({"id": "test-pipe-101"}).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(del_req) as resp:
        assert resp.status == 200
        data = json.loads(resp.read().decode("utf-8"))
        assert data["deleted"] is True
