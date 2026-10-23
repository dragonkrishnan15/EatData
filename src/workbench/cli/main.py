"""Command-line interface for the EatData workbench.

Invariants:
- All core workflows (import, profile, transform, export) execute strictly offline.
- Exit codes: 0 on success, 1 on validation/user error, 2 on internal crash.
- Source files are preserved; destination conflicts require --overwrite.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from datetime import UTC
from pathlib import Path

from workbench.adapters.exporters.csv_exporter import CsvExporter
from workbench.adapters.exporters.json_exporter import JsonExporter
from workbench.adapters.importers.csv_importer import CsvImporter
from workbench.adapters.importers.json_importer import JsonImporter
from workbench.domain.dataset import Dataset
from workbench.domain.errors import WorkbenchError
from workbench.domain.pipeline import Pipeline
from workbench.engine.profiler import Profiler
from workbench.engine.registry import TransformationRegistry


def load_dataset(file_path: Path) -> Dataset:
    """Load dataset using the appropriate format importer."""
    ext = file_path.suffix.lower()
    if ext in (".csv", ".tsv", ".txt"):
        importer = CsvImporter()
        return importer.import_file(file_path).dataset
    elif ext in (".json", ".ndjson", ".jsonl"):
        importer = JsonImporter()
        return importer.import_file(file_path).dataset
    else:
        raise WorkbenchError(f"Unsupported input format: '{ext}'. Supported: .csv, .json")


def save_dataset(
    dataset: Dataset,
    output_path: Path,
    source_path: Path | None = None,
    overwrite: bool = False,
    safe_csv: bool = True,
) -> None:
    """Export dataset to the destination path using the appropriate exporter."""
    ext = output_path.suffix.lower()
    if ext in (".csv", ".tsv"):
        exporter = CsvExporter(safe_csv_mode=safe_csv)
        exporter.export(dataset, output_path, source_path=source_path, overwrite=overwrite)
    elif ext == ".json":
        json_exporter = JsonExporter(layout="records")
        json_exporter.export(dataset, output_path, source_path=source_path, overwrite=overwrite)
    elif ext in (".ndjson", ".jsonl"):
        ndjson_exporter = JsonExporter(layout="ndjson")
        ndjson_exporter.export(dataset, output_path, source_path=source_path, overwrite=overwrite)
    else:
        raise WorkbenchError(f"Unsupported output format: '{ext}'. Supported: .csv, .json, .ndjson")


def cmd_profile(args: argparse.Namespace) -> int:
    input_path = Path(args.input_path)
    dataset = load_dataset(input_path)
    profiler = Profiler()
    profile = profiler.profile(dataset)

    if args.format == "json":
        import json

        sys.stdout.write(json.dumps(profile.to_dict(), indent=2) + "\n")
        return 0

    # Human-readable table
    sys.stdout.write(f"\nDataset Profile: {profile.dataset_name}\n")
    sys.stdout.write(f"{'=' * 60}\n")
    sys.stdout.write(f"Rows:               {profile.row_count}\n")
    sys.stdout.write(f"Columns:            {profile.column_count}\n")
    sys.stdout.write(f"Duplicate Rows:     {profile.duplicate_row_count}\n")
    sys.stdout.write(f"Total Missing:      {profile.total_null_count}\n")
    sys.stdout.write("\nColumns Overview:\n")
    sys.stdout.write(f"{'-' * 60}\n")
    sys.stdout.write(f"{'Column Name':<25} {'Type':<12} {'Null %':<10} {'Distinct':<10}\n")
    sys.stdout.write(f"{'-' * 60}\n")
    for name, col in profile.columns.items():
        col_type = col.inferred_type.value
        null_pct = f"{col.null_percentage:.1f}"
        sys.stdout.write(
            f"{name[:24]:<25} {col_type:<12} {null_pct:<10} {col.distinct_count:<10}\n"
        )
    sys.stdout.write(f"{'-' * 60}\n\n")

    if profile.warnings:
        sys.stdout.write("Warnings:\n")
        for w in profile.warnings:
            sys.stdout.write(f" - {w}\n")
        sys.stdout.write("\n")

    return 0


def cmd_pipeline_validate(args: argparse.Namespace) -> int:
    pipe_path = Path(args.pipeline_path)
    if not pipe_path.exists():
        sys.stderr.write(f"Error: Pipeline file not found: {pipe_path}\n")
        return 1

    content = pipe_path.read_text(encoding="utf-8")
    pipeline = Pipeline.from_json(content)
    sys.stdout.write(f"Pipeline '{pipeline.name}' (version {pipeline.version}) is valid.\n")
    sys.stdout.write(f"Total steps: {len(pipeline.steps)}\n")

    if args.dataset:
        ds_path = Path(args.dataset)
        dataset = load_dataset(ds_path)
        warnings = pipeline.validate_against_dataset(dataset)
        if warnings:
            sys.stdout.write("\nDataset Validation Warnings:\n")
            for w in warnings:
                sys.stdout.write(f" - {w}\n")
        else:
            sys.stdout.write("All steps successfully validated against dataset schema.\n")

    return 0


def cmd_pipeline_save(args: argparse.Namespace) -> int:
    from workbench.adapters.storage.sqlite_repository import get_default_repository

    pipe_path = Path(args.pipeline_path)
    if not pipe_path.exists():
        sys.stderr.write(f"Error: Pipeline file not found: {pipe_path}\n")
        return 1

    content = pipe_path.read_text(encoding="utf-8")
    pipeline = Pipeline.from_json(content)
    repo = get_default_repository()
    repo.save_pipeline(pipeline, description=args.description or "")
    sys.stdout.write(f"Saved pipeline '{pipeline.name}' (ID: {pipeline.id}) to repository.\n")
    return 0


def cmd_pipeline_list(args: argparse.Namespace) -> int:
    from workbench.adapters.storage.sqlite_repository import get_default_repository

    repo = get_default_repository()
    pipelines = repo.list_pipelines()
    if not pipelines:
        sys.stdout.write("No saved pipelines found in local repository.\n")
        return 0

    sys.stdout.write(f"\nSaved Pipelines ({len(pipelines)} total):\n")
    sys.stdout.write(f"{'-' * 80}\n")
    sys.stdout.write(f"{'ID':<38} {'Name':<30} {'Version':<8}\n")
    sys.stdout.write(f"{'-' * 80}\n")
    for p in pipelines:
        sys.stdout.write(f"{p['id']:<38} {p['name'][:29]:<30} {p['version']:<8}\n")
    sys.stdout.write(f"{'-' * 80}\n\n")
    return 0


def cmd_transform(args: argparse.Namespace) -> int:
    import time
    import uuid
    from datetime import datetime

    from workbench.adapters.storage.sqlite_repository import JobRunRecord, get_default_repository

    input_path = Path(args.input_path)
    pipe_path = Path(args.pipeline)
    output_path = Path(args.output)

    dataset = load_dataset(input_path)
    content = pipe_path.read_text(encoding="utf-8")
    pipeline = Pipeline.from_json(content)

    t0 = time.perf_counter()
    status = "success"
    err_msg: str | None = None
    reports = []
    final_ds = dataset

    try:
        registry = TransformationRegistry()
        final_ds, reports = registry.execute_pipeline(dataset, pipeline)

        save_dataset(
            final_ds,
            output_path=output_path,
            source_path=input_path,
            overwrite=args.overwrite,
        )
    except Exception as err:
        status = "failed"
        err_msg = str(err)
        raise
    finally:
        elapsed_ms = (time.perf_counter() - t0) * 1000.0
        total_affected = sum(r.rows_affected for r in reports)
        try:
            repo = get_default_repository()
            repo.record_job_run(
                JobRunRecord(
                    id=str(uuid.uuid4()),
                    pipeline_id=pipeline.id,
                    pipeline_name=pipeline.name,
                    input_filename=input_path.name,
                    rows_before=dataset.row_count,
                    rows_after=final_ds.row_count,
                    rows_affected=total_affected,
                    execution_time_ms=round(elapsed_ms, 2),
                    status=status,
                    error_message=err_msg,
                    executed_at=datetime.now(UTC).isoformat(),
                )
            )
        except Exception as storage_err:
            sys.stderr.write(f"Warning: Failed to persist job run telemetry: {storage_err}\n")

    sys.stdout.write("Successfully transformed dataset:\n")
    sys.stdout.write(f" - Input:        {input_path} ({dataset.row_count} rows)\n")
    sys.stdout.write(f" - Output:       {output_path} ({final_ds.row_count} rows)\n")
    sys.stdout.write(f" - Steps Run:    {len(reports)}\n")
    for r in reports:
        sys.stdout.write(f"   * {r.operation_name}: {r.rows_affected} rows affected\n")

    return 0


def cmd_history_list(args: argparse.Namespace) -> int:
    from workbench.adapters.storage.sqlite_repository import get_default_repository

    repo = get_default_repository()
    runs = repo.list_job_runs(limit=args.limit, status=args.status)
    if not runs:
        sys.stdout.write("No execution history records found.\n")
        return 0

    sys.stdout.write(f"\nExecution History ({len(runs)} displayed):\n")
    sys.stdout.write(f"{'-' * 80}\n")
    header = f"{'Executed At':<20} {'Pipeline':<20} {'File':<18} {'Status':<8} {'Time (ms)':<10}\n"
    sys.stdout.write(header)
    sys.stdout.write(f"{'-' * 80}\n")
    for r in runs:
        exec_at = r.executed_at[:19].replace("T", " ")
        p_name = r.pipeline_name[:19]
        f_name = r.input_filename[:17]
        sys.stdout.write(
            f"{exec_at:<20} {p_name:<20} {f_name:<18} {r.status:<8} {r.execution_time_ms:<10.1f}\n"
        )
    sys.stdout.write(f"{'-' * 80}\n\n")
    return 0


def cmd_history_purge(args: argparse.Namespace) -> int:
    from workbench.adapters.storage.sqlite_repository import get_default_repository

    repo = get_default_repository()
    deleted = repo.purge_job_runs(older_than_days=args.older_than_days)
    if args.older_than_days:
        sys.stdout.write(
            f"Purged {deleted} history records older than {args.older_than_days} days.\n"
        )
    else:
        sys.stdout.write(f"Purged all {deleted} execution history records.\n")
    return 0


def cmd_export(args: argparse.Namespace) -> int:
    input_path = Path(args.input_path)
    output_path = Path(args.output)
    dataset = load_dataset(input_path)

    save_dataset(
        dataset,
        output_path=output_path,
        source_path=input_path,
        overwrite=args.overwrite,
    )

    sys.stdout.write(f"Exported {dataset.row_count} rows to '{output_path}'.\n")
    return 0


def cmd_ui(args: argparse.Namespace) -> int:
    import webbrowser

    from workbench.ui.server import WorkbenchServer

    port = int(args.port)
    server = WorkbenchServer(host="127.0.0.1", port=port)
    server.start()
    url = f"http://127.0.0.1:{server.port}"
    sys.stdout.write(f"\nEatData Offline Workbench UI running at:\n  {url}\n\n")
    sys.stdout.write("Press Ctrl+C to stop.\n")
    if not getattr(args, "no_browser", False):
        try:
            webbrowser.open(url)
        except Exception:
            pass
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        sys.stdout.write("\nShutting down EatData Workbench.\n")
    finally:
        server.shutdown()
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="workbench",
        description="EatData — Deterministic offline data processing workbench.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # profile
    p_profile = subparsers.add_parser("profile", help="Profile dataset schema and quality.")
    p_profile.add_argument("input_path", help="Path to input dataset (CSV, JSON).")
    p_profile.add_argument(
        "--format", choices=["table", "json"], default="table", help="Output format."
    )
    p_profile.set_defaults(func=cmd_profile)

    # pipeline
    p_pipe = subparsers.add_parser("pipeline", help="Pipeline inspection and validation.")
    pipe_subs = p_pipe.add_subparsers(dest="subcommand", required=True)
    p_pipe_val = pipe_subs.add_parser("validate", help="Validate a pipeline definition JSON.")
    p_pipe_val.add_argument("pipeline_path", help="Path to pipeline JSON file.")
    p_pipe_val.add_argument("--dataset", help="Optional path to dataset to validate schema.")
    p_pipe_val.set_defaults(func=cmd_pipeline_validate)

    p_pipe_save = pipe_subs.add_parser("save", help="Save a pipeline JSON into repository.")
    p_pipe_save.add_argument("pipeline_path", help="Path to pipeline JSON file.")
    p_pipe_save.add_argument("--description", default="", help="Optional description.")
    p_pipe_save.set_defaults(func=cmd_pipeline_save)

    p_pipe_list = pipe_subs.add_parser("list", help="List saved pipelines in repository.")
    p_pipe_list.set_defaults(func=cmd_pipeline_list)

    # history
    p_hist = subparsers.add_parser("history", help="Inspect and manage transformation history.")
    hist_subs = p_hist.add_subparsers(dest="subcommand", required=True)
    p_hist_list = hist_subs.add_parser("list", help="List past transformation runs.")
    p_hist_list.add_argument("--limit", type=int, default=50, help="Maximum records to show.")
    p_hist_list.add_argument(
        "--status", choices=["success", "failed", "cancelled"], help="Filter by status."
    )
    p_hist_list.set_defaults(func=cmd_history_list)

    p_hist_purge = hist_subs.add_parser(
        "purge", help="Retention control: delete execution history records."
    )
    p_hist_purge.add_argument(
        "--older-than-days", type=int, default=None, help="Purge records older than N days."
    )
    p_hist_purge.set_defaults(func=cmd_history_purge)

    # transform
    p_trans = subparsers.add_parser("transform", help="Apply a pipeline to clean a dataset.")
    p_trans.add_argument("input_path", help="Path to input dataset.")
    p_trans.add_argument("--pipeline", required=True, help="Path to pipeline JSON.")
    p_trans.add_argument("--output", required=True, help="Destination output path.")
    p_trans.add_argument("--overwrite", action="store_true", help="Allow overwrite of output file.")
    p_trans.set_defaults(func=cmd_transform)

    # export
    p_export = subparsers.add_parser("export", help="Convert/export a dataset to another format.")
    p_export.add_argument("input_path", help="Path to input dataset.")
    p_export.add_argument("--output", required=True, help="Destination output path.")
    p_export.add_argument(
        "--overwrite", action="store_true", help="Allow overwrite of output file."
    )
    p_export.set_defaults(func=cmd_export)

    # ui
    p_ui = subparsers.add_parser("ui", help="Launch the local desktop UI.")
    p_ui.add_argument("--port", type=int, default=8080, help="Local port to bind (default: 8080).")
    p_ui.add_argument(
        "--no-browser", action="store_true", help="Do not automatically launch web browser."
    )
    p_ui.set_defaults(func=cmd_ui)

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    try:
        args = parser.parse_args(argv)
        return args.func(args)
    except WorkbenchError as err:
        sys.stderr.write(f"Workbench Error: {err.user_message}\n")
        return 1
    except Exception as err:
        sys.stderr.write(f"Unexpected Error: {err}\n")
        return 2


if __name__ == "__main__":
    sys.exit(main())
