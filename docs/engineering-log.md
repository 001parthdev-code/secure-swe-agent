# Secure SWE Agent — Engineering Log

Status terms: **observed**, **pending**, **hypothesis**, **known limitation**. A successful compilation is not a security proof.

## 2026-10-21 — E1 baseline (observed on Windows)
- **Objective:** Introduce a read-only, default-deny Rust enforcer.
- **Assumptions:** Agent-supplied requests and paths are untrusted; the launcher controls `ENFORCER_WORKSPACE`.
- **Hypothesis:** Relative-path checks, canonicalization and symlink checks prevent simple escape attempts.
- **Changes:** JSON Lines protocol, read-only policy, 1 MiB file-read limit, 64 KiB request limit, unit tests.
- **Evidence:** User-provided Windows terminal output: `cargo test` 5 passed; `cargo clippy --all-targets -- -D warnings` passed. `cargo fmt --check` initially showed formatting diffs; user subsequently reported formatting completed. No Linux results provided.
- **Limitations:** Check-then-open filesystem race; Windows junction/reparse-point behavior unverified. E1 is not a secure filesystem sandbox.

## 2026-10-21 — E1 security hardening iteration 2 (implementation; validation pending)
- **Objective:** Make protocol framing consistent and add adversarial regression tests.
- **Assumptions:** JSON Lines may use LF or CRLF; malicious callers may send malformed or oversized input.
- **Hypothesis:** Trimming line terminators before the payload-size check prevents spurious rejection. Cross-platform tests can identify path-validation gaps.
- **Changes:** `main.rs` trims LF/CRLF before parsing and adjusts the oversized-line threshold; adds request validation tests. `policy.rs` adds path escape tests and Windows-only drive/UNC/junction tests. Documentation structure established.
- **Verification:** NOT RUN in the assistant environment (Rust toolchain unavailable). Run commands in `docs/experiments/E1-security-validation.md` on Windows and Linux.
- **Open questions:** Junction test may expose a real bypass. Race-free file opening remains unsolved. Do not advance to E2 on the strength of these tests alone.
