# E4 Functional Audit — 2026-10-25

## Objective
Emit machine-readable metadata-only audit events for every processed CLI request without changing stdout JSON response contracts.

## Design
- The trusted CLI emits one JSONL record to stderr for each request, including malformed and denied requests.
- Fields: schema, per-process sequence, wall-clock milliseconds, action, status, request size.
- Do not include file paths, file contents, tokens, command strings, response output, or error text.
- Audit write errors terminate the CLI rather than silently continuing to process subsequent requests.
- CI smoke test checks the stdout/stderr separation and malformed-input audit event.

## Explicit limitations
- Stderr is a **stream**, not durable storage. A supervisor must capture and protect it; without capture, audit records may be lost.
- Audit is emitted after an operation and before its response; an abrupt crash can leave an unaudited operation.
- Not tamper-evident, globally ordered, crash-durable, or a production security attestation.
- Privileged parent must prevent untrusted code from replacing the audit sink.
- E2 exclusive-authority and E3 filesystem confinement remain independent release blockers for hostile production workloads.

## Verification
Run Cargo fmt/test/clippy and `python3 scripts/verify-e4-audit.py` on Linux CI. Results pending.
