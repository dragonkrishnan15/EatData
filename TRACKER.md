# Project Tracker

Legend: `TODO`, `IN_PROGRESS`, `BLOCKED`, `DONE`. Update status and evidence in the same change.

## Current phase

**Phase:** M1 — Local engine  
**Overall status:** IN_PROGRESS  
**Current next task:** Implement CSV importer with limits and structured errors (M1-01).  
**Last verified:** 2026-10-23 (27 unit and security tests passing, ruff lint/format clean).

## Task board

| ID | Status | Task | Depends on | Acceptance / evidence |
|---|---|---|---|---|
| M0-01 | DONE | Inspect repository, Python version, git status, and existing files | None | Git repo initialized (`main`), Python 3.15 + uv 0.13.0 verified. Remote tracking configured. |
| M0-02 | DONE | Set up package, test runner, formatter/linter, and dependency policy | M0-01 | `pyproject.toml` created, hatchling build, pytest 9.1.1 + ruff 0.17.2 verified clean. |
| M0-03 | DONE | Define Dataset, Profile, Operation, Pipeline, and structured error contracts | M0-01 | Domain models created in `src/workbench/domain/`, 21 unit tests passing. |
| M0-04 | DONE | Add synthetic CSV/JSON fixtures including malformed and edge-case data | M0-01 | 9 synthetic fixtures in `tests/fixtures/`, zero secrets or real data verified via tests. |
| M0-05 | DONE | Add privacy tests and threat-model review | M0-03, M0-04 | `THREAT_MODEL.md` created; `tests/security/` verifies redaction and allowlist invariants. |
| M1-01 | TODO | Implement CSV importer with limits and structured errors | M0-02, M0-03 | Import tests pass |
| M1-02 | TODO | Implement JSON importer with nesting/resource limits | M0-02, M0-03 | Import tests pass |
| M1-03 | TODO | Implement local profiler | M1-01, M1-02 | Counts and inferred types tested |
| M1-04 | TODO | Implement allowlisted transformations and pipeline validator | M0-03 | Deterministic operation tests pass |
| M1-05 | TODO | Implement preview and execution semantics | M1-04 | Preview agrees with execution for supported operations |
| M1-06 | TODO | Implement CSV/JSON export without source overwrite by default | M1-05 | Round-trip and conflict tests pass |
| M1-07 | TODO | Build CLI profile/transform/export workflow | M1-03, M1-06 | CLI integration tests pass |
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

## Update protocol

For each task update, record:
- Status.
- Date.
- Files changed.
- Commands/tests executed and actual results.
- Any remaining failure or blocker.

Never mark `DONE` based solely on code being written. Require evidence.
