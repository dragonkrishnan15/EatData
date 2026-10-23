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
