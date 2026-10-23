# Threat Model & Security Architecture

## 1. Scope & System Boundaries

EatData processes potentially sensitive tabular data (financial records, customer metrics, inventory lists, operations logs) strictly on the user's local machine.

```text
+-------------------------------------------------------------------------+
| Local User Machine (TRUSTED BOUNDARY)                                   |
|                                                                         |
|  [Source Files] ---> [Safe Importer] ---> [In-Memory Dataset]           |
|                                                   |                     |
|                                            [Local Engine]               |
|                                             (Deterministic)             |
|                                                   |                     |
|  [Export File] <--- [Safe Exporter] <-------------+                     |
|                                                   |                     |
|                                          [Metadata Builder]             |
|                                                   | (Allowlist only)    |
|                                          [Consent Gate]                 |
+---------------------------------------------------|---------------------+
                                                    | (HTTPS Outbound)
+---------------------------------------------------|---------------------+
| External AI Providers (UNTRUSTED BOUNDARY)        v                     |
|   - OpenAI / Anthropic / Gemini / Local Ollama  [API Payload]           |
|                                                   |                     |
|   <--- Untrusted JSON Recipe ---------------------+                     |
+-------------------------------------------------------------------------+
```

---

## 2. Threat Analysis & Mitigations

### Threat 1: Sensitive Data Exfiltration via AI Payloads
- **Risk**: User data (raw rows, personal identifiers, account numbers, file paths) sent over the network to third-party LLMs.
- **Impact**: High (Confidentiality breach, regulatory violation).
- **Mitigations**:
  1. Core features (import, profile, transform, export) have zero network connectivity.
  2. `MetadataBuilder` employs an explicit allowlist. It is architecturally impossible for raw row objects or raw cell values to be passed to the builder.
  3. Default payload excludes high-cardinality values, raw file paths, and unredacted headers if privacy mode is enabled.
  4. Mandatory consent modal renders the exact outgoing JSON payload prior to any network request.
  5. Automated security test suite scans all provider payloads for simulated PII/raw fixtures.

### Threat 2: Arbitrary Code Execution via Untrusted AI Recipes
- **Risk**: An LLM returns code, shell scripts, Python snippets, or dangerous instructions that get executed on the host.
- **Impact**: Critical (Host compromise).
- **Mitigations**:
  1. AI outputs only a structured JSON recipe, never executable code.
  2. Absolute prohibition of `eval()`, `exec()`, `os.system()`, subprocess calls, or dynamic imports on model outputs.
  3. Recipes are parsed against a strict JSON Schema and checked against an allowlist of registered transformations.
  4. Unknown keys, unsupported operations, non-existent columns, or out-of-range parameters are rejected immediately.

### Threat 3: Host Resource Exhaustion / Malformed Input Denial of Service
- **Risk**: Pathological CSV files with unbounded lines, deeply nested JSON, or multi-gigabyte files causing memory crashes.
- **Impact**: Medium (Availability loss, desktop crash).
- **Mitigations**:
  1. Maximum file size, row count, column count, and JSON nesting depth limits enforced before loading.
  2. Streaming/chunked readers with cancellation checks.
  3. Type inference uses bounded sampling, avoiding expensive regex scans on millions of cells.

### Threat 4: Spreadsheet Formula Injection in Exported Files
- **Risk**: Cleaned CSV files opened in Excel or Google Sheets execute formulas starting with `=`, `+`, `-`, `@`, `\t`, or `\r`.
- **Impact**: High (Code execution on consumer spreadsheets).
- **Mitigations**:
  1. Dedicated `SafeExportMode` sanitizes cell text beginning with formula triggers by prefixing with a single quote `'` or escaping characters.
  2. Export options display formula-sanitization settings explicitly.

### Threat 5: Credential Leakage in Application Logs and History
- **Risk**: API keys stored in plain text, checked into Git, or printed in error tracebacks.
- **Impact**: High (Unauthorized access to user AI accounts).
- **Mitigations**:
  1. API keys are loaded via the OS credential manager (Keyring) or environment variables; never written to plain-text configuration files.
  2. Structured loggers filter and redact Authorization headers and known key patterns.
  3. Exception handlers sanitize contextual error messages before presenting them to the user.

### Threat 6: Insecure Local Model Endpoints (SSRF / Unauthenticated Access)
- **Risk**: Connecting to an untrusted or non-loopback Ollama endpoint that could forward traffic or execute unauthorized commands.
- **Impact**: Medium to High.
- **Mitigations**:
  1. Validate endpoint URLs (defaulting to `http://localhost:11434` or `http://127.0.0.1:11434`).
  2. Explicitly notify the user if an endpoint points to a non-loopback IP address.
  3. Enforce request timeouts and response size bounds.

---

## 3. Security Verification Checklist

Every pull request and milestone must verify:
- [ ] No outbound network calls during import, profile, transform, export.
- [ ] AI payload regression tests pass (`test_ai_payload_never_contains_raw_rows`).
- [ ] Host execution tests pass (`test_recipe_validator_rejects_eval_and_scripts`).
- [ ] Formula injection sanitization tests pass (`test_csv_export_sanitizes_formula_triggers`).
- [ ] Zero secrets in SQLite history or logs (`test_history_redaction`).
