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
