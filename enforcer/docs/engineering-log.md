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

## E1 final hardening candidate — 2026-10-21
- **Assumption:** Untrusted paths can contain intermediate reparse points; the workspace is provisioned by a trusted operator.
- **Hypothesis:** Opening one NT component at a time relative to retained handles closes the intermediate-reparse gap.
- **Change:** Replaced multi-component Windows native open with handle-relative traversal; tightened JSONL oversized-frame detection; added targeted regressions.
- **Observation:** Source patch prepared from uploaded repository; no local Rust toolchain available to execute tests.
- **Result:** Pending Windows/Linux CI and native API review. E1 **not yet accepted**.

## 2026-10-22 — Isolation preflight foundation (implementation candidate)
- **Problem:** The eight-crate migration created an empty isolation crate, but no OS-enforced mutation boundary exists.
- **Assumption:** Same-user processes can bypass ordinary workspace mode-bit restrictions; directory metadata alone is not proof of isolation.
- **Hypothesis:** An explicit fail-closed isolation readiness contract prevents the transaction engine from mistaking a private directory for an enforced boundary.
- **Change:** Added `inspect_workspace`, immutable inspection findings, and a mutation-readiness check that refuses unverified workspaces. Added cross-platform tests and ADR-004.
- **Verification:** Rust compilation, tests, and CI pending. No native OS sandbox has been implemented.
- **Next:** Implement separate-identity OS isolation backends and adversarial direct-write tests before enabling versioned modification.

## 2026-10-22 — Windows DACL preflight (implementation candidate)
- **Assumption:** Workspace root may be attacker-influenced; a null DACL is unsafe.
- **Hypothesis:** Native security-descriptor inspection can reject obviously unsafe roots without claiming isolation.
- **Changes:** Added Windows-only `inspect_windows_dacl` with descriptor lifetime management and fail-closed root checks; added Windows-only tests and ADR-006.
- **Verification:** Not executed in the authoring environment; Windows CI pending.
- **Limitation:** No Windows restricted child process or effective-access denial has been verified. This is a preflight, not the promised full Windows isolation backend. `modify_file_versioned` remains denied.
