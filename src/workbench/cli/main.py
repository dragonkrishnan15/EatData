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


def cmd_transform(args: argparse.Namespace) -> int:
    input_path = Path(args.input_path)
    pipe_path = Path(args.pipeline)
    output_path = Path(args.output)

    dataset = load_dataset(input_path)
    content = pipe_path.read_text(encoding="utf-8")
    pipeline = Pipeline.from_json(content)

    registry = TransformationRegistry()
    final_ds, reports = registry.execute_pipeline(dataset, pipeline)

    save_dataset(
        final_ds,
        output_path=output_path,
        source_path=input_path,
        overwrite=args.overwrite,
    )

    sys.stdout.write("Successfully transformed dataset:\n")
    sys.stdout.write(f" - Input:        {input_path} ({dataset.row_count} rows)\n")
    sys.stdout.write(f" - Output:       {output_path} ({final_ds.row_count} rows)\n")
    sys.stdout.write(f" - Steps Run:    {len(reports)}\n")
    for r in reports:
        sys.stdout.write(f"   * {r.operation_name}: {r.rows_affected} rows affected\n")

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
