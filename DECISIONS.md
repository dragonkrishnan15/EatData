# Architectural Decision Records (ADRs)

## ADR-001: Tooling and Environment Strategy
- **Status**: Decided
- **Context**: The project requires a deterministic, isolated Python runtime with pinned dependencies, fast testing, and linting.
- **Decision**: Use `uv` as the package and virtual environment manager (`uv venv`, `uv run`). Use `pytest` for test execution, `ruff` for linting and formatting.
- **Consequences**: Fast dependency resolution, zero global environment pollution, strictly reproducible builds.

## ADR-002: Baseline Repository Structure
- **Status**: Decided
- **Context**: `RULES.md` and `ARCHITECTURE.md` require modular isolation: domain logic independent of UI, CLI, or AI providers.
- **Decision**: Organize codebase under `src/workbench/` into `domain`, `engine`, `adapters`, `application`, `cli`, and `visualization` modules. Tests under `tests/unit`, `tests/integration`, `tests/security`, and `tests/fixtures`.
- **Consequences**: Clean dependency graph, no circular dependencies, clear security boundaries.

## ADR-003: Desktop UI Shell Architecture
- **Status**: Decided
- **Context**: The desktop UI must fulfill `DESIGN.md` with dark theme, high information density, side-by-side cell diff highlighting, and interactive charts, while strictly operating 100% offline with zero cloud assets or heavy runtime overhead.
- **Decision**: Provide a local-first desktop application shell bound strictly to loopback `127.0.0.1`. The backend exposes lightweight JSON API endpoints invoking `src/workbench/application/` use cases. The frontend is a self-contained, offline single-page application built with vanilla HTML5, CSS3, and ES6 (zero external CDN or remote font/script requests).
- **Consequences**: 100% offline, zero NPM build dependencies, cross-platform compatibility across Windows/macOS/Linux, instantaneous startup, and full testability via HTTP integration tests.

## ADR-004: Zero-Dependency Excel Ingestion Strategy
- **Status**: Decided
- **Context**: Ingesting Excel `.xlsx` files typically pulls in heavy third-party dependencies (`openpyxl`, `pandas`) which bloat distribution size and create security/license attack surfaces.
- **Decision**: Implement `ExcelImporter` in `src/workbench/adapters/importers/excel_importer.py` using Python's standard library `zipfile` and `xml.etree.ElementTree`. Enforce strict resource limits (`max_file_size_bytes`, `max_rows`, `max_columns`), resolve sheet names from `xl/workbook.xml` relationships, and parse `xl/sharedStrings.xml` without any third-party dependencies.
- **Consequences**: Zero new dependencies added to `pyproject.toml`, pure offline execution, high-performance streaming XML parsing, and safe handling of malicious or oversized archives.

## ADR-005: Deterministic Pipeline Replay & Token-based Theming
- **Status**: Decided
- **Context**: In previous versions, removing or undoing a pipeline step left the in-memory dataset mutated. The UI also lacked density controls, keyboard shortcuts, and table sorting/filtering.
- **Decision**: 
  1. The client maintains an immutable `rawBaselineDataset`. Any pipeline modification (add, remove, toggle, undo, redo) replays all enabled steps from the raw baseline via `POST /api/transform`, guaranteeing 100% deterministic mathematical consistency.
  2. The UI table implements sorting (toggle ascending/descending with sort glyphs), live multi-column substring filtering, and pagination (25/50/100/All rows).
  3. UI theming uses CSS custom properties (`theme-dark`, `theme-light`, `theme-slate`) and density modes (`density-comfortable`, `density-compact`), persisted in `localStorage`.
  4. Pipelines can be saved and loaded directly from the local SQLite repository via `/api/pipelines/*`.
- **Consequences**: Zero state drift between pipeline steps and dataset preview, seamless keyboard accessibility (`Ctrl+Z`, `Ctrl+Y`), adaptable visual density for serious data work.

