"""Local desktop UI loopback HTTP server.

Invariants:
- STRICT PRIVACY: Bound exclusively to loopback interface 127.0.0.1 (Rule 10).
- Remote network interface binding (e.g. 0.0.0.0) is rejected at startup.
- Serves self-contained offline SPA assets (zero external requests).
- Exposes local JSON API for import, profiling, transformations, preview diffs, charts, and exports.
"""

from __future__ import annotations

import email
import json
import logging
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from workbench.adapters.exporters.csv_exporter import CsvExporter
from workbench.adapters.exporters.json_exporter import JsonExporter
from workbench.adapters.importers.csv_importer import CsvImporter
from workbench.adapters.importers.json_importer import JsonImporter
from workbench.domain.dataset import Dataset
from workbench.domain.errors import SecurityError, ValidationError
from workbench.domain.operations import Operation
from workbench.domain.pipeline import Pipeline
from workbench.engine.preview import PreviewEngine
from workbench.engine.profiler import Profiler
from workbench.engine.registry import TransformationRegistry
from workbench.visualization.chart_data import ChartDataService
from workbench.visualization.chart_spec import ChartSpec, ChartType

logger = logging.getLogger("workbench.ui.server")
HTML_PATH = Path(__file__).parent / "app.html"


class WorkbenchRequestHandler(BaseHTTPRequestHandler):
    """HTTP request handler for local loopback data workbench UI and API."""

    server_version = "EatDataWorkbench/1.0"

    def do_GET(self) -> None:
        """Handle GET requests."""
        if self.path in ("/", "/index.html"):
            self._serve_html()
        elif self.path == "/api/health":
            self._send_json({"status": "ok", "app": "EatData Offline Workbench"})
        else:
            self._send_error_json(HTTPStatus.NOT_FOUND, f"Endpoint '{self.path}' not found.")

    def do_POST(self) -> None:
        """Handle POST requests."""
        try:
            if self.path == "/api/import":
                self._handle_import()
            elif self.path == "/api/profile":
                self._handle_profile()
            elif self.path == "/api/preview":
                self._handle_preview()
            elif self.path == "/api/transform":
                self._handle_transform()
            elif self.path == "/api/chart":
                self._handle_chart()
            elif self.path == "/api/export":
                self._handle_export()
            else:
                self._send_error_json(HTTPStatus.NOT_FOUND, f"Unknown API endpoint: {self.path}")
        except ValidationError as err:
            self._send_error_json(HTTPStatus.BAD_REQUEST, str(err))
        except Exception as err:
            logger.exception("Internal error processing %s", self.path)
            self._send_error_json(HTTPStatus.INTERNAL_SERVER_ERROR, f"Internal error: {err}")

    def _serve_html(self) -> None:
        if not HTML_PATH.exists():
            self._send_error_json(HTTPStatus.NOT_FOUND, "UI asset app.html not found.")
            return
        content = HTML_PATH.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(content)))
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(content)

    def _read_body_bytes(self) -> bytes:
        length = int(self.headers.get("Content-Length", 0))
        if length <= 0:
            return b""
        return self.rfile.read(length)

    def _read_body_json(self) -> dict[str, Any]:
        raw = self._read_body_bytes().decode("utf-8")
        if not raw:
            return {}
        try:
            return json.loads(raw)
        except Exception as err:
            raise ValidationError(f"Invalid JSON payload: {err}") from err

    def _send_json(self, data: Any, status: HTTPStatus = HTTPStatus.OK) -> None:
        body = json.dumps(data).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_error_json(self, status: HTTPStatus, message: str) -> None:
        body = json.dumps({"error": str(status.phrase), "message": message}).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _handle_import(self) -> None:
        content_type = self.headers.get("Content-Type", "")

        # Option A: Multipart file upload
        if "multipart/form-data" in content_type:
            body = self._read_body_bytes()
            # Parse multipart using email Message
            msg_bytes = f"Content-Type: {content_type}\r\nMIME-Version: 1.0\r\n\r\n".encode() + body
            msg = email.message_from_bytes(msg_bytes)
            uploaded_filename = "uploaded_file.csv"
            file_data: bytes | None = None

            for part in msg.walk():
                if part.get_content_disposition() == "form-data":
                    fname = part.get_filename()
                    if fname:
                        uploaded_filename = fname
                        file_data = part.get_payload(decode=True)
                        break

            if file_data is None:
                raise ValidationError("No file attached in multipart upload.")

            # Create temporary dataset via stream or temp file
            import tempfile

            suffix = Path(uploaded_filename).suffix.lower()
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                tmp.write(file_data)
                tmp_path = Path(tmp.name)

            try:
                if suffix == ".json":
                    dataset = JsonImporter().import_file(tmp_path).dataset
                else:
                    dataset = CsvImporter().import_file(tmp_path).dataset
                # Set name to original file name
                dataset = Dataset(
                    id=dataset.id,
                    name=Path(uploaded_filename).name,
                    columns=dataset.columns,
                    rows=dataset.rows,
                )
            finally:
                if tmp_path.exists():
                    tmp_path.unlink()

        # Option B: JSON payload with filepath or direct content
        else:
            payload = self._read_body_json()
            filepath = payload.get("filepath")
            if not filepath:
                raise ValidationError("Import requires multipart upload or 'filepath' in JSON.")
            p = Path(filepath)
            if not p.exists():
                raise ValidationError(f"File not found: {filepath}")
            if p.suffix.lower() == ".json":
                dataset = JsonImporter().import_file(p).dataset
            else:
                dataset = CsvImporter().import_file(p).dataset

        profiler = Profiler()
        profile = profiler.profile(dataset)
        self._send_json({"dataset": dataset.to_dict(), "profile": profile.to_dict()})

    def _handle_profile(self) -> None:
        payload = self._read_body_json()
        ds_data = payload.get("dataset")
        if not ds_data:
            raise ValidationError("Payload missing 'dataset'.")
        dataset = Dataset.from_dict(ds_data)
        profile = Profiler().profile(dataset)
        self._send_json({"profile": profile.to_dict()})

    def _handle_preview(self) -> None:
        payload = self._read_body_json()
        ds_data = payload.get("dataset")
        op_data = payload.get("operation")
        if not ds_data or not op_data:
            raise ValidationError("Preview requires 'dataset' and 'operation'.")
        dataset = Dataset.from_dict(ds_data)
        op = Operation.from_dict(op_data)
        preview_engine = PreviewEngine(TransformationRegistry())
        result = preview_engine.preview_operation(dataset, op)
        self._send_json(
            {
                "preview": result.to_dict(),
                "modified_cells": result.modified_cells,
            }
        )

    def _handle_transform(self) -> None:
        payload = self._read_body_json()
        ds_data = payload.get("dataset")
        pipe_data = payload.get("pipeline")
        if not ds_data or not pipe_data:
            raise ValidationError("Transform requires 'dataset' and 'pipeline'.")
        dataset = Dataset.from_dict(ds_data)
        pipeline = Pipeline.from_dict(pipe_data)

        registry = TransformationRegistry()
        transformed, _ = registry.execute_pipeline(dataset, pipeline)
        profile = Profiler().profile(transformed)
        self._send_json(
            {
                "dataset": transformed.to_dict(),
                "profile": profile.to_dict(),
            }
        )

    def _handle_chart(self) -> None:
        payload = self._read_body_json()
        ds_data = payload.get("dataset")
        spec_data = payload.get("spec")
        if not ds_data or not spec_data:
            raise ValidationError("Chart requires 'dataset' and 'spec'.")
        dataset = Dataset.from_dict(ds_data)
        chart_type = ChartType(spec_data.get("chart_type", "bar"))
        spec = ChartSpec(
            chart_type=chart_type,
            title=str(spec_data.get("title", "Chart")),
            x_column=spec_data.get("x_column"),
            y_column=spec_data.get("y_column"),
            aggregation=str(spec_data.get("aggregation", "count")),
            max_bins=int(spec_data.get("max_bins", 15)),
        )
        service = ChartDataService()
        data = service.build_chart_data(dataset, spec)
        self._send_json(data)

    def _handle_export(self) -> None:
        payload = self._read_body_json()
        ds_data = payload.get("dataset")
        filename = payload.get("filename")
        if not ds_data or not filename:
            raise ValidationError("Export requires 'dataset' and 'filename'.")
        dataset = Dataset.from_dict(ds_data)
        out_path = Path(filename).resolve()
        overwrite = bool(payload.get("overwrite", True))

        if out_path.suffix.lower() == ".json":
            res = JsonExporter().export(dataset, out_path, overwrite=overwrite)
        else:
            res = CsvExporter().export(dataset, out_path, overwrite=overwrite)

        self._send_json(
            {
                "status": "ok",
                "rows_exported": res.rows_exported,
                "destination_path": str(res.destination_path),
            }
        )

    def log_message(self, format: str, *args: Any) -> None:
        """Suppress default stdout request logging to avoid terminal clutter."""
        logger.debug(format, *args)


class WorkbenchServer:
    """Server runner encapsulating the loopback HTTP server."""

    def __init__(self, host: str = "127.0.0.1", port: int = 8080) -> None:
        # Strict Rule 10 enforcement: only loopback interfaces permitted
        if host not in ("127.0.0.1", "localhost", "::1"):
            raise SecurityError(
                f"Prohibited host '{host}'. "
                "Workbench server must strictly bind to loopback (127.0.0.1)."
            )
        self.host = host
        self.port = port
        self.server: ThreadingHTTPServer | None = None

    def start(self) -> None:
        """Start the HTTP server on the configured loopback host and port."""
        self.server = ThreadingHTTPServer((self.host, self.port), WorkbenchRequestHandler)
        # Update port in case port=0 was passed for ephemeral testing port
        self.port = self.server.server_address[1]

    def serve_forever(self) -> None:
        """Serve requests indefinitely until interrupted."""
        if not self.server:
            self.start()
        assert self.server is not None
        self.server.serve_forever()

    def shutdown(self) -> None:
        """Stop and close the HTTP server."""
        if self.server:
            self.server.shutdown()
            self.server.server_close()
            self.server = None
