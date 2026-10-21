# E1 adversarial validation protocol

**Status:** Pending execution. Record actual outputs; do not replace them with expectations.

## Hypotheses
- H1: Malformed, unsupported and oversized JSON Lines requests are rejected.
- H2: Relative path traversal and absolute paths cannot read outside the workspace.
- H3: Windows junctions and other reparse points cannot redirect a read outside the workspace. **Not established; current implementation may fail this test.**
- H4: LF and CRLF are both accepted without changing the payload limit.

## Procedure
From `enforcer/` on Windows PowerShell and on Linux:

```sh
cargo fmt --check
cargo test
cargo clippy --all-targets -- -D warnings
```

Record OS version, Rust version (`rustc --version`), exact commands, test counts and failures. Windows junction test attempts to create a junction; if unavailable it prints a message and is not evidence of rejection. Do not interpret a skipped branch as a pass of H3.

## Results
| Platform | Formatting | Unit tests | Clippy | Junction behavior |
|---|---|---|---|---|
| Windows | Pending this iteration | Pending this iteration | Pending this iteration | Pending |
| Linux | Pending | Pending | Pending | Not applicable |

## Exit criteria
All tests pass on both platforms; junction behavior is exercised and verified; remaining race-condition weakness is eliminated with atomic OS-specific file opening or E1 is explicitly classified as a non-security-grade prototype. Until then E1 is **open**.

## Iteration 2 observed Windows results
- `cargo fmt --check`: no reported differences.
- `cargo test`: 9 passed, 0 failed.
- `cargo clippy --all-targets -- -D warnings`: passed.
- Junction test printed `The filename, directory name, or volume label syntax is incorrect.` despite returning `ok`. **H3 not verified.**

## Iteration 3 verification protocol
- Apply the patch, run `cargo fmt` once, then `cargo fmt --check`, `cargo test`, and `cargo clippy --all-targets -- -D warnings`.
- The Windows junction test now **fails** if it cannot construct the test junction. A setup failure must be investigated; it is not evidence of an Enforcer bypass or of protection.
- Push to GitHub to trigger `.github/workflows/enforcer-ci.yml` on Windows and Ubuntu. The workflow uses `--locked`; ensure `enforcer/Cargo.lock` is committed if present locally. If absent, generate and commit it using `cargo generate-lockfile`.
- Record OS versions, Rust versions, test output, and CI run URLs here.
- **Do not mark E1 complete:** TOCTOU mitigation remains an open security requirement even if all CI jobs pass.
