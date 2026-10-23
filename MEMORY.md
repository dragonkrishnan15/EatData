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
- **Git**: Initialized on `master` branch.
- **Package & Dependency Tooling**: `uv` 0.13.0, Python 3.15.0 (managed / available via `uv` and `py`).
- **Initial Documentation**:
  - `RULES.md`: 42 engineering invariants and workflow rules.
  - `PLAN.md`: Product roadmap and milestones (M0 through M6).
  - `ARCHITECTURE.md`: Component layout, domain contracts, provider contracts, and safety boundaries.
  - `TRACKER.md`: Active milestone task board and execution log.
  - `DECISIONS.md`: Architectural decision records (ADRs).
