# E2 final review — current status (2026-10-21)

## Verified baseline

User reported Windows 17/17 tests and both Windows and Ubuntu CI green on the prior E2 candidate. These results predate this patch.

## Hypothesis and change

A failed staged Windows write can leave a temporary file because the previous implementation omitted cleanup. This patch requests deletion through the already-owned temporary-file handle (`FileDispositionInformation`, class 13), avoiding a pathname-based cleanup race. If cleanup fails, the error is surfaced.

## Security findings still open

- **P0 — destination identity race:** Windows `modify_file` still validates a destination and later replaces by name; another actor can change that entry between the two operations. The same check-then-rename identity issue exists on Linux. Neither is solved by this cleanup patch.
- **P1 — temporary-file lifecycle:** handle-based deletion is implemented for Windows, but needs runtime verification and failure injection. Crash recovery and staged-file naming/cleanup also require a design.
- **P1 — OS error handling:** native errors are collapsed in parts of the Windows layer.

## Acceptance status

NOT COMPLETE. Do not expose E2 writes to an untrusted autonomous agent. Run fmt/test/Clippy and cross-platform CI; then resolve the P0 commit semantics. No test results for this patch are claimed.

## Architectural decision required

Choose whether `modify_file` means (A) replace the pathname's current entry atomically, or (B) replace only the exact file object originally authorized, rejecting concurrent substitution. The current API implies B but the implementation only approximates A. A fully correct B requires a platform-specific commit protocol or a restriction on concurrent writers.
