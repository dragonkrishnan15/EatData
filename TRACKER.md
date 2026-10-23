# Project Tracker

Legend: `TODO`, `IN_PROGRESS`, `BLOCKED`, `DONE`. Update status and evidence in the same change.

## Current phase

**Phase:** M5 — Packaging and hardening  
**Overall status:** IN_PROGRESS  
**Current next task:** Package and smoke-test on supported OS targets (M5-01).  
**Last verified:** 2026-10-23 (118 unit, storage, visualization, AI, security, CLI, and UI integration tests passing, ruff clean).

## Task board

| ID | Status | Task | Depends on | Acceptance / evidence |
|---|---|---|---|---|
| M0-01 | DONE | Inspect repository, Python version, git status, and existing files | None | Git repo initialized (`main`), Python 3.15 + uv 0.13.0 verified. Remote tracking configured. |
| M0-02 | DONE | Set up package, test runner, formatter/linter, and dependency policy | M0-01 | `pyproject.toml` created, hatchling build, pytest 9.1.1 + ruff 0.17.2 verified clean. |
| M0-03 | DONE | Define Dataset, Profile, Operation, Pipeline, and structured error contracts | M0-01 | Domain models created in `src/workbench/domain/`, 21 unit tests passing. |
| M0-04 | DONE | Add synthetic CSV/JSON fixtures including malformed and edge-case data | M0-01 | 9 synthetic fixtures in `tests/fixtures/`, zero secrets or real data verified via tests. |
| M0-05 | DONE | Add privacy tests and threat-model review | M0-03, M0-04 | `THREAT_MODEL.md` created; `tests/security/` verifies redaction and allowlist invariants. |
| M1-01 | DONE | Implement CSV importer with limits and structured errors | M0-02, M0-03 | `CsvImporter` implemented; tests in `test_csv_importer.py` pass. |
| M1-02 | DONE | Implement JSON importer with nesting/resource limits | M0-02, M0-03 | `JsonImporter` implemented; flattening & limits tested in `test_json_importer.py`. |
| M1-03 | DONE | Implement local profiler | M1-01, M1-02 | `Profiler` implemented; type inference & metrics tested in `test_profiler.py`. |
| M1-04 | DONE | Implement allowlisted transformations and pipeline validator | M0-03 | 12 pure transformations & `TransformationRegistry` tested in `test_transformations.py`. |
| M1-05 | DONE | Implement preview and execution semantics | M1-04 | `PreviewEngine` implemented; verified preview agrees with execution in `test_preview.py`. |
| M1-06 | DONE | Implement CSV/JSON export without source overwrite by default | M1-05 | `CsvExporter` & `JsonExporter` with atomic writes, formula injection defense tested. |
| M1-07 | DONE | Build CLI profile/transform/export workflow | M1-03, M1-06 | `workbench` CLI implemented; integration tests in `test_cli.py` pass. |
| M2-01 | DONE | Evaluate UI shell and prototype primary workflow | M1-07 | Recorded ADR-003 in `DECISIONS.md`. Self-contained offline desktop UI bound strictly to `127.0.0.1`. |
| M2-02 | DONE | Implement import/profile/clean/preview/export UI | M2-01 | Built `app.html`, `server.py`, `ChartDataService`, wired `workbench ui` command. Integration tested in `test_ui_server.py`. |
| M3-01 | DONE | Add SQLite schema and migration strategy | M1-07 | Transactional migrations, `schema_migrations`, pipelines, job runs, settings in `sqlite_repository.py`. |
| M3-02 | DONE | Add pipeline history and retention controls | M3-01 | Telemetry runs recorded, retention purge implemented and tested. Privacy verified via `test_storage_privacy.py`. |
| M4-01 | DONE | Define metadata allowlist and payload preview | M1-03 | `MetadataPackageBuilder` with column aliasing and SHA-256 payload preview tested in `test_metadata_builder.py`. |
| M4-02 | DONE | Define AI provider interface and router | M4-01 | `AIProvider`, `ConsentGate`, `AIRouter`, and `MockAIProvider` implemented and tested. |
| M4-03 | DONE | Add strict recipe schema and validator | M0-03, M4-02 | `RecipeValidator` enforces `ALLOWLISTED_OPERATIONS`, rejects code injection and arbitrary python in `test_recipe_validator.py`. |
| M4-04 | DONE | Integrate first cloud provider behind consent gate | M4-02, M4-03 | `CloudAIProvider` implemented with secret safety and `test_providers.py`. |
| M4-05 | DONE | Integrate Ollama adapter and endpoint safety checks | M4-02, M4-03 | `OllamaProvider` with loopback enforcement (refusing remote host endpoints) tested in `test_providers.py`. |
| M5-01 | TODO | Package and smoke-test on supported OS targets | M2-02, M4-05 | Reproducible build and install test recorded |
| M6-01 | TODO | Evaluate additional formats and industry templates | M5-01 | Prioritized by user evidence |
| M6-02 | TODO | Threat-review MCP server mode | M5-01 | Authentication/permissions/network boundary reviewed |

## Blockers

- Maximum file size and performance target are undecided.
- Desktop shell and dataframe engine are undecided.

## Work log

### M0 Milestone Completed: Repository & Contracts (2026-10-23)
- Created missing foundational documents: `README.md`, `DESIGN.md`, `THREAT_MODEL.md`.
- Formatted `pyproject.toml` with `hatchling`, configured `pytest` and `ruff`.
- Initialized Python environment with `uv` (installed `pytest==9.1.1`, `pytest-cov==7.1.0`, `ruff==0.17.2`).
- Defined core domain models in `src/workbench/domain/`:
  - `Dataset`, `ColumnMetadata`, `DataType` (immutable containers, safe `__repr__` without row leaking)
  - `DatasetProfile`, `ColumnProfile` (statistical summaries, allowlisted safe metadata)
  - `Operation`, `OperationName`, `ALLOWLISTED_OPERATIONS` (strict allowlist validation)
  - `Pipeline` (reproducible step sequence, add/remove/reorder/toggle, schema validation, JSON roundtrip)
  - `WorkbenchError` and structured error hierarchy in `errors.py`.
- Added 9 synthetic CSV and JSON fixtures in `tests/fixtures/` (clean, messy, malformed, empty, header-only, formula-injection, nested).
- Implemented unit and security tests in `tests/unit/domain/`, `tests/unit/test_fixtures.py`, `tests/security/test_privacy_invariants.py`.
- Verified 27 tests passing, `ruff check` clean, `ruff format` clean.
- All M0 tasks (M0-01 to M0-05) marked DONE. Transitioned to M1.

### M1 Milestone Completed: Local Engine (2026-10-23)
- Implemented `CsvImporter` with streaming, delimiter/BOM detection, resource limits, and ragged-row padding.
- Implemented `JsonImporter` with nested dictionary flattening, JSON lines (NDJSON) support, and depth limits.
- Implemented `Profiler` computing row/col counts, duplicate rows, missingness, distinct counts, min/max/mean, and type inference with uncertainty metrics.
- Implemented allowlisted transformations in `transformations.py`: `trim_whitespace`, `normalize_headers`, `rename_column`, `reorder_columns`, `cast_type`, `fill_missing`, `drop_duplicates`, `filter_rows`, `drop_columns`, `select_columns`, `split_column`, `combine_columns`.
- Implemented `TransformationRegistry` for single-step and multi-step pipeline execution.
- Implemented `PreviewEngine` generating before-and-after slices with cell diff coordinates. Verified Rule 17 preview agreement with execution.
- Implemented `CsvExporter` and `JsonExporter` with atomic replacement, destination conflict detection, source overwrite prevention, and safe CSV formula-injection neutralization.
- Implemented `workbench` CLI with `profile`, `pipeline validate`, `transform`, and `export` commands.
- Total 72 tests passing across unit, security, and CLI integration suites. Ruff linting and formatting 100% clean.
- All M1 tasks (M1-01 to M1-07) marked DONE. Transitioned to M2.

### M2 Milestone Completed: Usable First Interface (2026-10-23)
- Recorded ADR-003 in `DECISIONS.md` selecting a loopback-bound (`127.0.0.1`) self-contained single-page desktop UI (zero external CDN or internet dependencies).
- Implemented `ChartSpec` and `ChartDataService` in `src/workbench/visualization/` supporting bar, histogram, line, scatter, and missingness visualizations on aggregated metrics.
- Built responsive dark-themed desktop single-page application in `src/workbench/ui/app.html` with dataset overview, quality summary badges, interactive data table with modified cell diff highlights, column profiling, transformation pipeline builder, and distribution charts.
- Implemented `WorkbenchServer` in `src/workbench/ui/server.py` using Python `http.server` strictly bound to `127.0.0.1` (rejecting external interfaces to enforce Rule 10), with REST endpoints for import, profiling, prospective preview diffs, pipeline transformations, chart aggregations, and safe exports.
- Added `workbench ui [--port 8080] [--no-browser]` command to CLI with auto-browser launch option.
- Implemented unit tests for chart data service (`tests/unit/visualization/test_chart_data.py`) and full integration tests for UI server (`tests/integration/test_ui_server.py`).
- 86 tests passing, ruff lint and format 100% clean.
- All M2 tasks (M2-01 and M2-02) marked DONE. Transitioned to M3.

### M3 Milestone Completed: Persistence and Reproducibility (2026-10-23)
- Implemented transactional schema migration manager in `src/workbench/adapters/storage/schema.py` tracking versioning via `schema_migrations`.
- Implemented `SqliteRepository` in `src/workbench/adapters/storage/sqlite_repository.py` with WAL mode and foreign key enforcement, persisting pipeline specifications, execution telemetry (`job_runs`), and application settings.
- Enforced STRICT PRIVACY INVARIANT (Rules 2, 6, 14): SQLite schemas never contain tables or columns for raw data rows or cell contents. Verified via binary file inspection in `tests/security/test_storage_privacy.py`.
- Implemented retention and purge controls: `purge_job_runs(older_than_days)` allowing selective or complete deletion of execution history.
- Wired storage into CLI with `workbench pipeline save`, `workbench pipeline list`, `workbench history list`, and `workbench history purge`.
- All M3 tasks (M3-01 and M3-02) marked DONE. Transitioned to M4.

### M4 Milestone Completed: Optional AI Assistance (2026-10-23)
- Implemented `MetadataPackageBuilder` in `src/workbench/adapters/ai/metadata.py` extracting schema, statistical quality summaries, and pattern types without sample values or cell contents. Added reversible column aliasing mode and deterministic SHA-256 payload hashing.
- Implemented `RecipeValidator` in `src/workbench/adapters/ai/recipe_schema.py` enforcing strict validation against `ALLOWLISTED_OPERATIONS`, rejecting arbitrary Python code execution, eval, imports, and unauthorized root/step keys.
- Implemented `AIProvider` base interface and `ConsentGate` in `src/workbench/adapters/ai/base.py`, strictly requiring explicit user consent prior to external transmission. Built offline deterministic `MockAIProvider`.
- Implemented `OllamaProvider` with loopback security check (strictly refusing remote hosts unless authorized) and `CloudAIProvider` with secret protection.
- Implemented `AIRouter` orchestrating provider calls, unaliasing column recipes, and validating returned recipes into executable `Pipeline` objects.
- Wired AI into CLI via `workbench ai propose` (supporting `--preview-payload`, `--consent`, `--alias-columns`) and UI server via `/api/ai/preview-payload` and `/api/ai/propose`.
- Total 118 tests passing across all suites. Ruff linting and formatting 100% clean.
- All M4 tasks (M4-01 through M4-05) marked DONE. Transitioned to M5.

## Update protocol

For each task update, record:
- Status.
- Date.
- Files changed.
- Commands/tests executed and actual results.
- Any remaining failure or blocker.

Never mark `DONE` based solely on code being written. Require evidence.
