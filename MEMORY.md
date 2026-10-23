# Project Memory

## Overview
**Project**: Local-First Data Workbench (`EatDataAnylst`)  
**Mission**: A trustworthy, deterministic, local-first data workbench for inspecting data quality, applying reversible cleaning operations, previewing transformations, creating visual summaries, and exporting results without mandatory cloud services.

## Core Invariants & Rules Reference
- **Local processing by default**: Zero outbound network requests for import, profile, clean, preview, or export.
- **Privacy & Redaction**: No raw rows, raw cells, file paths, or secrets sent to external AI or written to logs.
- **Deterministic transforms**: Fixed input + pipeline = identical output.
- **Allowlisted AI recipes**: Optional AI produces only versioned JSON recipes matching an explicit allowlist of operations; never execute arbitrary code.
- **Source preservation**: Source files are read-only; never overwrite original inputs without explicit confirmation.

## Environment Facts (Baseline)
- **OS**: Windows (win32)
- **Git**: Branch `main`, tracking remote `origin` (`https://github.com/dragonkrishnan15/EatData.git`).
- **Package & Dependency Tooling**: `uv` 0.13.0, Python 3.15.0 (managed / available via `uv` and `py`).
- **Documentation Assets**:
  - `README.md`: Vision, workflow, principles, getting started.
  - `RULES.md`: 42 engineering invariants and workflow rules.
  - `PLAN.md`: Product roadmap and milestones (M0 through M6).
  - `ARCHITECTURE.md`: Component layout, domain contracts, provider contracts, and safety boundaries.
  - `DESIGN.md`: UI specification, layout, color tokens, and interaction states.
  - `THREAT_MODEL.md`: Threat vectors, mitigations, and security verification checklist.
  - `TRACKER.md`: Active milestone task board and execution log.
  - `DECISIONS.md`: Architectural decision records (ADRs).

## Milestone Status
- **M0 (Repository & Contracts)**: Completed.
  - Package configured via `hatchling` in `pyproject.toml`.
  - Tooling: `pytest` 9.1.1, `ruff` 0.17.2, `pytest-cov` 7.1.0 in `.venv`.
  - Domain models in `src/workbench/domain/`: `Dataset`, `ColumnMetadata`, `DataType`, `DatasetProfile`, `ColumnProfile`, `Operation`, `OperationName`, `Pipeline`, `errors.py`.
  - Test coverage: 27 automated unit and security tests passing.
- **M1 (Local Engine)**: Completed.
  - `CsvImporter` and `JsonImporter` with streaming, flattening, delimiter/encoding detection, and resource bounds.
  - `Profiler` with statistical distributions, null/duplicate/empty tracking, and confidence-scored type inference.
  - Pure allowlisted `transformations.py` and `TransformationRegistry` supporting 12 operations.
  - `PreviewEngine` generating deterministic before/after cell diffs agreeing with execution semantics (Rule 17).
  - Safe `CsvExporter` and `JsonExporter` with atomic replacement, overwrite protection, and formula-injection defense.
  - `workbench` CLI fully functional (`profile`, `pipeline validate`, `transform`, `export`).
  - Total test suite: 72 tests passing across unit, security, and CLI integration tests.
- **M2 (Usable First Interface)**: Next phase.
  - Immediate task: `M2-01` (Evaluate desktop UI shell and prototype primary workflow).
