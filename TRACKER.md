# Project Tracker

Legend: `TODO`, `IN_PROGRESS`, `BLOCKED`, `DONE`. Update status and evidence in the same change.

## Current phase

**Phase:** M2 — Usable first interface  
**Overall status:** TODO  
**Current next task:** Evaluate UI shell and prototype primary workflow (M2-01).  
**Last verified:** 2026-10-23 (72 unit, security, and CLI integration tests passing, ruff clean).

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
| M2-01 | TODO | Evaluate UI shell and prototype primary workflow | M1-07 | Decision recorded with trade-offs |
| M2-02 | TODO | Implement import/profile/clean/preview/export UI | M2-01 | Primary journey tested |
| M3-01 | TODO | Add SQLite schema and migration strategy | M1-07 | Migration and corruption tests pass |
| M3-02 | TODO | Add pipeline history and retention controls | M3-01 | History contains no raw rows or secrets |
| M4-01 | TODO | Define metadata allowlist and payload preview | M1-03 | Tests prove excluded values never appear |
| M4-02 | TODO | Define AI provider interface and router | M4-01 | Mock-provider contract tests pass |
| M4-03 | TODO | Add strict recipe schema and validator | M0-03, M4-02 | Adversarial recipe tests pass |
| M4-04 | TODO | Integrate first cloud provider behind consent gate | M4-02, M4-03 | Tests plus manual consent verification |
| M4-05 | TODO | Integrate Ollama adapter and endpoint safety checks | M4-02, M4-03 | Local endpoint behavior documented and tested |
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

## Update protocol

For each task update, record:
- Status.
- Date.
- Files changed.
- Commands/tests executed and actual results.
- Any remaining failure or blocker.

Never mark `DONE` based solely on code being written. Require evidence.
