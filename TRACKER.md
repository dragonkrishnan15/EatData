# Project Tracker

Legend: `TODO`, `IN_PROGRESS`, `BLOCKED`, `DONE`. Update status and evidence in the same change.

## Current phase

**Phase:** M0 — Repository and contracts  
**Overall status:** TODO  
**Current next task:** Inspect/create repository baseline and define domain contracts.  
**Last verified:** Not yet verified.

## Task board

| ID | Status | Task | Depends on | Acceptance / evidence |
|---|---|---|---|---|
| M0-01 | DONE | Inspect repository, Python version, git status, and existing files | None | Git repo initialized (`master`), Python 3.15 + uv 0.13.0 verified. Initial files preserved. |
| M0-02 | TODO | Set up package, test runner, formatter/linter, and dependency policy | M0-01 | Clean test/lint run documented |
| M0-03 | TODO | Define Dataset, Profile, Operation, Pipeline, and structured error contracts | M0-01 | Unit tests for validation and serialization |
| M0-04 | TODO | Add synthetic CSV/JSON fixtures including malformed and edge-case data | M0-01 | Fixtures contain no real sensitive data |
| M0-05 | TODO | Add privacy tests and threat-model review | M0-03, M0-04 | Tests verify payload/log redaction invariants |
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

### Baseline Setup (2026-10-23)
- Inspected repository baseline: existing files `ARCHITECTURE.md`, `PLAN.md`, `RULES.md`, `TRACKER.md`.
- Detected Python environment: `uv` 0.13.0 and Python 3.15 installed.
- Initialized local git repository on branch `master`.
- Added standard `.gitignore`, `MEMORY.md`, and `DECISIONS.md` (ADR-001, ADR-002).
- M0-01 marked DONE.

## Update protocol

For each task update, record:
- Status.
- Date.
- Files changed.
- Commands/tests executed and actual results.
- Any remaining failure or blocker.

Never mark `DONE` based solely on code being written. Require evidence.
