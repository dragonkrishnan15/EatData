# Product Plan

## 1. Vision

Build a trustworthy local-first data workbench for people who repeatedly receive inconsistent CSV, Excel, JSON, and database exports. Users should be able to understand data quality, apply reversible cleaning steps, create charts, and export results without needing a cloud service.

## 2. Problem statement

Common data workflows involve manual spreadsheet cleanup, inconsistent column names and types, duplicated rows, malformed values, repeated merges, and undocumented transformations. These workflows are slow and difficult to reproduce.

## 3. Target users

Initial hypotheses, to validate through interviews:
- Analysts and operations teams handling spreadsheet exports.
- Agencies combining marketing or advertising reports.
- Small businesses cleaning invoices, inventory, or sales exports.
- Users who prefer local processing because of confidentiality or connectivity constraints.

Do not market the product as certified for healthcare, banking, government, or regulated workloads until applicable security, legal, deployment, and compliance requirements have been assessed independently.

## 4. Product principles

1. Local processing is the default.
2. AI is optional; core workflows must not depend on it.
3. Never silently transmit file contents or metadata.
4. Cleaning actions are inspectable, previewable, and reproducible.
5. Destructive actions require preview and clear confirmation.
6. Fail safely: preserve source files and report partial failures.
7. Prefer explicit supported formats over claims of handling “any file format.”
8. Provide evidence for privacy and security claims.

## 5. MVP scope

### In scope
- Import CSV and JSON; add Excel after the CSV workflow is stable.
- Read-only source handling: never overwrite the original input by default.
- File and dataset profile: row/column counts, inferred types, missingness, duplicate counts, basic distributions, parse errors.
- Local transformations: trim whitespace, normalize headers, convert types, handle missing values, remove duplicates with a preview, filter rows, rename/drop columns, split/merge columns where safe.
- Transformation pipeline represented as versioned structured steps.
- Preview before applying; undo/redo within the current session if feasible.
- Export cleaned output to CSV and JSON; preserve encoding and document limitations.
- Basic charts: bar, line, histogram, scatter, and missing-value overview where appropriate.
- Local run history that excludes raw rows and secrets.
- CLI for profiling, running a pipeline, and exporting.
- Automated unit and integration tests.

### Explicitly out of scope for MVP
- Arbitrary binary/document formats.
- Editing a live production database.
- Automatic execution of arbitrary AI-generated Python, SQL, shell, or code.
- Cloud storage/sync, telemetry by default, user accounts, team collaboration.
- Compliance certifications or guarantees.
- Complex ETL scheduling and distributed processing.
- MCP server exposure until permissioning and local-service security are reviewed.

## 6. AI assistance design

### Modes
- **No AI:** fully local workflow.
- **Local model:** user-configured local Ollama endpoint; network binding and endpoint must be checked and explained.
- **Cloud provider:** user supplies their own API key and explicitly enables a provider.

### Metadata-only proposal
The app may construct a minimal metadata package containing schema, inferred types, aggregate quality indicators, and carefully chosen pattern summaries. Before transmission, show the exact outgoing payload and require user consent for the first request and whenever its scope changes.

Column names and pattern summaries can themselves reveal sensitive information. Metadata-only is not equivalent to zero disclosure. Never send sample rows by default. Do not send free-text cell values, unique identifiers, secrets, or raw file paths.

### AI output
AI returns a proposed versioned JSON recipe using an allowlisted operation vocabulary. Validate schema, parameters, column references, resource limits, and operation compatibility. Show a human-readable plan and preview before execution. AI cannot execute code or bypass local validation.

## 7. Milestones

### M0 — Repository and contracts
- Establish Python version, package structure, formatting/linting, test runner, CI, and dependency policy.
- Define dataset, profile, transformation, pipeline, and error models.
- Create synthetic fixtures and threat-model review.

### M1 — Local engine
- CSV/JSON import with limits and clear errors.
- Profile generation.
- Deterministic transformations and preview.
- Export without overwriting source.
- CLI and automated tests.

### M2 — Usable first interface
- Local desktop UI with import, profile, transformation list, preview, chart, export.
- Progress, cancellation where supported, and useful errors.
- Test representative large files and memory use.

### M3 — Persistence and reproducibility
- SQLite for app settings, pipeline definitions, and history.
- Schema versioning and migrations.
- Redaction and retention controls.

### M4 — Optional AI
- Provider interface and router.
- Metadata preview/consent.
- JSON recipe validation and safe application.
- Cloud provider integration and local Ollama integration behind separate adapters.
- Tests for malformed, malicious, and oversized model output.

### M5 — Packaging and hardening
- Evaluate PyInstaller versus Tauri based on UX, footprint, update strategy, and platform needs.
- Build reproducible release artifacts.
- Review permissions, secrets storage, dependency licenses, logs, and security.
- Document supported platforms and known limitations.

### M6 — Advanced capabilities
- Additional formats, template packs, saved pipelines, database connectors, and MCP server mode only after core stability and threat review.

## 8. Definition of done

A task is done only when:
- Its acceptance criteria are met.
- Relevant automated tests pass.
- Errors and edge cases are handled.
- No raw data or secrets are accidentally added to logs or fixtures.
- Documentation and tracker are updated.
- Any security-sensitive behavior has been reviewed.
- The exact command and result used for verification are recorded.

## 9. Success measures

Measure locally and transparently:
- Import/profile success rate on representative fixtures.
- Correctness of transformation outputs.
- Peak memory and elapsed time on documented test datasets.
- Export round-trip correctness where applicable.
- Number of operations that can be reproduced from a saved pipeline.
- AI payload inspection and consent behavior.
- Crash/error recovery without source-file modification.

## 10. Open questions

- Final product name and supported OS targets.
- Expected maximum file size and memory budget.
- Whether pandas, Polars, or another engine best fits initial requirements.
- Desktop shell choice after core prototype.
- Excel formula, date, formatting, and multi-sheet behavior.
- Database connector scope and read-only defaults.
- Local model endpoint configuration and security assumptions.
