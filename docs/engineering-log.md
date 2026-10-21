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

## 2026-10-21 — E1 security hardening iteration 2 (Windows results received)
- **Observation:** User ran formatting, tests, and Clippy on Windows. Nine tests passed; Clippy passed; formatting check produced no output.
- **Critical caveat:** Junction test printed a Windows filename syntax error yet returned `ok`. This is a false-positive test outcome, not a verified junction denial.
- **Conclusion:** Protocol/path regression checks pass on Windows. Junction protection and race resistance are still unverified.

## 2026-10-21 — E1 iteration 3 (patch prepared; validation pending)
- **Objective:** Eliminate the silent junction-test bypass and establish Windows/Linux CI.
- **Assumptions:** `cmd.exe` and `mklink /J` are available on the Windows test runner; the workspace and target are local directories.
- **Hypothesis:** Failing explicitly on junction-creation errors will distinguish a tested denial from a test that never exercised the attack.
- **Changes:** Junction test now requires successful creation, verifies the junction exists, and captures command diagnostics. GitHub Actions matrix executes formatting, tests, and Clippy on Windows and Ubuntu.
- **Verification:** Not run in this environment (Rust toolchain unavailable). User and CI results pending.
- **Known limitation:** Current `symlink_metadata`/`canonicalize`/`File::open` sequence is vulnerable to concurrent path replacement (TOCTOU). Iteration 3 does NOT fix it; do not treat passing tests as proof of race resistance.
- **Next decision:** Implement atomic, handle-relative opening on both operating systems before declaring E1 secure.
