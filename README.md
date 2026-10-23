# EatData — Offline Data Workbench

> **Local engine processes the data. Optional AI proposes the recipe. The user stays in control.**

EatData is a trustworthy, deterministic, local-first desktop data workbench designed for analysts, data teams, and small organizations handling inconsistent CSV, JSON, and spreadsheet exports.

---

## Core Product Workflow

```text
Import → Inspect → Profile → Validate → Clean → Transform → Preview → Visualize → Export
```

1. **Import**: Local file ingestion with encoding detection, safe parsing, and resource limits. Source files are strictly preserved.
2. **Inspect & Profile**: Deterministic local calculation of schema, row/column counts, missingness, duplicate rows, distinct counts, and outlier indicators.
3. **Validate & Clean**: Registry of typed, allowlisted transformations with parameter validation and explicit strategies.
4. **Transform & Preview**: Full before-and-after previews and affected-row reporting before committing changes.
5. **Visualize**: Local charting (bar, line, histogram, scatter, missingness) derived purely from local dataset aggregates.
6. **Export**: Safe, atomic writing to new user-selected destinations, preserving types with optional CSV formula-injection mitigation.

---

## Privacy & Security Principles

- **100% Offline by Default**: Core parsing, profiling, cleaning, charting, and export require zero network access.
- **Strict Metadata Boundary**: If optional AI assistance is enabled, only an explicit allowlist of aggregated metadata (column names/types, missingness percentages, aggregate stats) can be transmitted.
- **Never Sent to AI**: Raw rows, cell values, source files, file paths, and credentials are prohibited from AI requests.
- **Untrusted Recipe Validation**: AI cannot execute code. It outputs versioned JSON recipes that are checked against an allowlist schema, parameter bounds, and local dataset columns before preview.
- **Safe Secrets Storage**: API credentials reside in the OS credential store, never in plaintext configs, logs, or repository files.

---

## Project Documentation Index

- [`PLAN.md`](PLAN.md): Product roadmap, milestones (M0–M6), scope boundaries, and acceptance criteria.
- [`RULES.md`](RULES.md): 42 mandatory engineering and security invariants.
- [`ARCHITECTURE.md`](ARCHITECTURE.md): System component topology, domain models, provider contracts, and error structures.
- [`DESIGN.md`](DESIGN.md): Desktop visual language, information hierarchy, and user interaction standards.
- [`THREAT_MODEL.md`](THREAT_MODEL.md): Threat analysis, attack vectors, mitigation strategies, and privacy test cases.
- [`TRACKER.md`](TRACKER.md): Active task board, milestone dependencies, and verification logs.
- [`DECISIONS.md`](DECISIONS.md): Architectural Decision Records (ADRs).
- [`MEMORY.md`](MEMORY.md): Durable session memory, runtime facts, and engineering handoffs.

---

## Development

The project is built using Python (3.12+) and managed with Astral `uv`.

```bash
# Setup environment & install dependencies
uv sync

# Run test suite
uv run pytest

# Format and lint
uv run ruff check .
uv run ruff format .
```
