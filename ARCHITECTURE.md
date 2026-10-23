# System Architecture

## 1. Architectural goals

- Local-first and deterministic core.
- UI independent from transformation logic.
- AI providers are optional adapters, not owners of data processing.
- Every transformation is typed, validated, and auditable.
- Testable module boundaries.
- No execution of arbitrary model-generated code.
- Resource limits and failure isolation for untrusted input files.

## 2. Proposed component map

```text
Desktop UI / CLI
       |
Application Services (use cases, orchestration, cancellation)
       |
       +---- Import Adapters ----> Local Dataset Model
       |                                |
       |                           Profiler
       |                                |
       +---- Pipeline Validator <--- Pipeline JSON
       |             |
       |       Transformation Registry
       |             |
       +-------- Local Engine --------> Result Dataset
       |                                  |
       +---- Chart Data Service           +---- Export Adapters
       |
       +---- AI Orchestrator (optional)
                    |
              Metadata Builder
                    |
          Payload Preview + Consent Gate
                    |
              Provider Router
              /             \
       Cloud Adapter     Ollama Adapter
              \             /
             Untrusted JSON recipe
                    |
             Recipe Validator
                    |
              Pipeline Preview

Local persistence: SQLite for settings, pipeline definitions, job metadata, history
Secrets: OS credential store where available; never plain-text config
```

## 3. Suggested package layout

```text
src/
  workbench/
    __init__.py
    cli/
      __init__.py
      main.py
    application/
      import_dataset.py
      profile_dataset.py
      apply_pipeline.py
      export_dataset.py
      suggest_recipe.py
    domain/
      dataset.py
      profile.py
      pipeline.py
      operations.py
      errors.py
    adapters/
      importers/
        csv_importer.py
        json_importer.py
      exporters/
        csv_exporter.py
        json_exporter.py
      ai/
        base.py
        router.py
        metadata.py
        recipe_schema.py
        openai_adapter.py
        ollama_adapter.py
      storage/
        sqlite_repository.py
        secrets.py
    engine/
      profiler.py
      executor.py
      registry.py
      validators.py
    visualization/
      chart_spec.py
      chart_data.py
tests/
  unit/
  integration/
  security/
  fixtures/
docs/
```

This is a proposal, not a claim that these files already exist. Keep the initial implementation smaller if the package structure would create empty abstractions.

## 4. Core domain contracts

### Dataset
A local, typed representation of a loaded dataset. Carries column metadata and a stable in-process reference. Avoid embedding raw rows in logs or exception strings.

### Profile
Contains row and column counts, inferred types with confidence/uncertainty, null counts, duplicate counts, parse failures, and bounded aggregate statistics. Profiling must not mutate the dataset.

### Operation
A typed allowlisted operation with a version, parameters, input requirements, and validation. Examples: `trim_whitespace`, `rename_column`, `cast_type`, `fill_missing`, `drop_duplicates`, `filter_rows`.

### Pipeline
An ordered list of versioned operations. Must be serializable to JSON, validated before execution, and reproducible with recorded operation versions and relevant settings.

### Recipe
An untrusted proposed pipeline from AI. Parse against a strict schema; reject unknown fields, operations, columns, excessive steps, invalid parameters, and unsafe resource requests.

## 5. Data flow

1. Importer reads an explicitly selected local file under size and resource limits.
2. Importer returns a dataset plus structured warnings/errors.
3. Profiler computes local statistics without mutating data.
4. User or AI proposes a pipeline.
5. Validator checks every operation and its parameters.
6. Preview computes the prospective result or a clearly labeled approximation.
7. User approves application.
8. Engine executes deterministic operations and emits a structured result.
9. Exporter writes to a new destination using safe temporary-file/atomic-replace patterns where supported.
10. History stores operation metadata, timestamps, result status, and pipeline version; no raw rows.

## 6. AI provider contract

Provider adapter should accept a validated request object and return untrusted text/JSON plus provider metadata. It must not receive the dataset object or a path to the source file.

Conceptual interface:

```python
class AIProvider:
    def generate_recipe(self, request: MetadataRequest) -> ProviderResponse: ...
```

The actual interface should support timeouts, cancellation if available, bounded response sizes, structured errors, and provider identification. Keep provider-specific request formats inside adapters.

## 7. Metadata boundary

`MetadataBuilder` should use an explicit allowlist. Default payload may include:
- Generic column identifiers and types.
- Missingness counts/percentages.
- Bounded aggregate statistics.
- Pattern categories such as “date-like” or “currency-like,” when safe.

Default payload must exclude:
- Raw rows and cell values.
- File contents, file paths, and credentials.
- Free-text samples.
- Direct identifiers and likely secrets.
- High-cardinality values that can reveal records.

Column names may contain personal or confidential information. Provide a local-only/alias-columns option and display the exact payload before cloud transmission.

## 8. Provider routing

- `none`: no AI request; no provider network activity.
- `ollama`: local endpoint configured by the user; verify endpoint and explain network binding. Do not assume every endpoint is loopback-only.
- Cloud provider: explicit provider selection, stored key retrieved at use time from OS credential storage where supported, request sent only after consent.
- Fail closed: unknown provider, missing consent, invalid key state, or malformed configuration must not trigger a fallback to another provider.
- Never log authorization headers or API keys.

## 9. Persistence

SQLite stores:
- App settings that are not secrets.
- Schema-versioned pipelines and transformation parameters.
- Job metadata, timestamps, and status.
- Redacted AI request/response metadata only if user has enabled history.

Never store raw rows in history. Decide retention limits and provide clear deletion controls. Apply migrations and handle corrupt databases safely.

## 10. Error model

Use structured error categories: unsupported format, parse failure, validation failure, resource limit, provider unavailable, consent required, invalid recipe, execution failure, export conflict, storage failure, cancellation. User-facing messages must be actionable and must not include sensitive values.

## 11. Performance and resource safety

- Set configurable limits for file size, rows, columns, nesting depth, pipeline steps, and AI response size.
- Avoid loading huge files blindly; consider chunked processing after MVP.
- Detect pathological JSON nesting and malformed inputs.
- Avoid unbounded regexes and expensive inference on every cell.
- Include cancellation checkpoints for long operations.
- Measure memory and latency on representative fixtures.

## 12. Testing strategy

- Unit tests for importers, profiler, validators, operations, recipe parser, and metadata allowlist.
- Integration tests for import → profile → transform → export.
- Security tests ensuring raw values and secrets never enter AI payloads or logs.
- Contract tests using mocked providers; no real API key required in CI.
- Golden tests for pipeline reproducibility.
- Packaging smoke tests on each supported OS.
