# Engineering Rules and Invariants

These rules are mandatory unless a documented decision explicitly changes a rule with a reason and risk review.

## A. Privacy and security

1. Local processing is the default. No network request is permitted for core import, profiling, cleaning, charting, or export.
2. No raw rows, cell values, source files, or file paths are sent to AI by default.
3. Every cloud AI request passes through the metadata builder and consent gate.
4. Show the exact outgoing payload, provider, and purpose before transmission. Re-consent if the payload scope materially changes.
5. Treat column names and aggregate statistics as potentially sensitive.
6. Never log API keys, authorization headers, raw rows, or unredacted provider request bodies.
7. Store API keys in the OS credential store where available. If unavailable, explain the limitation and require a deliberate secure fallback; never silently write plaintext keys.
8. Do not automatically switch from local to cloud AI after an error.
9. Validate AI output as untrusted input. No `eval`, `exec`, shell commands, dynamic imports, or arbitrary code execution from model output.
10. Do not bind a local service to all network interfaces by default. Explain and validate local model endpoints.
11. Keep source files unchanged by default. Export to a new path and require explicit confirmation before overwrite.
12. Minimize history and provide retention/deletion controls.

## B. Data correctness

13. Transformations must be deterministic for a fixed input, pipeline, and documented environment, except where a documented operation explicitly states otherwise.
14. Never silently discard rows or columns. Show counts and reasons.
15. Type inference is a hypothesis; display uncertainty and allow user correction.
16. Missing values, invalid values, parse failures, and actual zeros are distinct concepts.
17. Preview should match execution semantics. If it is sampled or approximate, label it clearly.
18. Validate all operation names, parameters, column references, and type requirements before execution.
19. Preserve provenance: source identity metadata, ordered operations, versions, and export summary, without storing raw data in logs.
20. Handle malformed and oversized input as untrusted content.

## C. Engineering quality

21. Keep domain logic independent of UI and provider-specific SDKs.
22. Provider adapters must not receive a full dataset object.
23. Use typed interfaces and structured errors at module boundaries.
24. Add tests with each new behavior and regression tests for every fixed bug.
25. Use synthetic fixtures. Never commit real customer, medical, financial, or other sensitive data.
26. Pin or constrain dependencies, review licenses, and avoid unnecessary packages.
27. Keep functions focused and names explicit. Avoid hidden global state.
28. Add timeouts, response-size limits, and resource limits at external/input boundaries.
29. No broad exception swallowing. If an exception is converted to a user-safe error, preserve diagnostic context locally without sensitive payloads.
30. Do not claim tests, scans, builds, or manual checks ran unless they actually ran.

## D. AI recipe rules

31. AI outputs a versioned JSON recipe only.
32. The recipe schema uses an allowlist of operations.
33. Reject unknown keys, unsupported operations, invalid column names, excessive steps, and oversized responses.
34. Show proposed actions and a preview before applying.
35. Never let the model choose an arbitrary output path, access the filesystem, or invoke a tool without a separate permissioned interface.
36. Record provider/model identifiers and recipe version when useful, but never secrets or raw data.

## E. Documentation and workflow

37. Read `MEMORY.md`, `RULES.md`, and `TRACKER.md` before implementation work.
38. Update `TRACKER.md` whenever task state changes.
39. Update `ARCHITECTURE.md` and `DECISIONS.md` when boundaries or architectural choices change.
40. Keep completed tasks backed by test evidence.
41. Do not mark a proposal as implemented merely because its documentation exists.
42. If requirements conflict, stop and record the conflict rather than quietly violating a privacy or correctness invariant.
