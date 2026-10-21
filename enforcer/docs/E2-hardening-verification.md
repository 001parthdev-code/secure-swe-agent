# E2 write hardening — verification record

## Baseline
The initial E2 candidate passed 15 Windows tests and Clippy, as reported by the operator. Its Windows modify path used `FILE_OVERWRITE`, which can truncate the destination before validation.

## Assumptions
- Supported Windows target for the native rename layout is **x86_64 Windows 10/11**. Linux target remains kernel 5.6+.
- Workspace root is trusted when opened. The attacker can supply paths and concurrently alter workspace directory entries.
- Filesystem-specific rename semantics, access-control policy, and durable storage behavior require deployment-specific evaluation.

## Hypothesis
Staging complete bytes in a new file under a pinned parent directory and renaming the staged file prevents a partially written destination and avoids modifying a reparse target through a followed link.

## Changes
- Windows: replaced destructive `FILE_OVERWRITE` with an exclusively created temporary file, complete write and flush, then handle-based NT rename relative to the retained parent directory.
- Windows: validates destination without write/truncate access, rejects intermediate and final reparse points, and uses no-replace semantics for creation.
- Added regression tests for rejected writes preserving existing data and successful replacement of longer content with shorter content.

## Limits / security review findings
- Windows temporary files may remain after failed writes. Cleanup is not performed via attacker-controlled pathnames. Operational cleanup must be implemented safely before long-running deployments.
- A concurrent attacker may replace the destination directory entry between its validation and the rename. Rename stays within the pinned parent directory, but **modify-only authorization of a particular object identity is not guaranteed**.
- Windows NT rename implementation uses a manually constructed native ABI buffer; it needs independent review and runtime verification on supported Windows versions. This is a **candidate**, not an audited production-ready security boundary.
- NT rename may fail depending on file-sharing modes and filesystem behavior. Failures must leave the original destination intact.
- Linux modify similarly validates an existing entry before a later rename. It does not guarantee object-identity stability under concurrent replacement.
- Atomic rename is a single-file namespace operation, not a multi-file transaction or universal crash-durability guarantee.

## Verification required
1. `cargo fmt --check`, `cargo test --locked`, `cargo clippy --locked --all-targets -- -D warnings` on Windows and Ubuntu.
2. Confirm Windows create and modify tests exercise the actual NT rename operation.
3. Add deterministic concurrent destination-substitution tests and audit the Windows FFI layout and rename semantics before untrusted-agent deployment.
4. Verify failed write behavior and leftover temporary-file handling.

## Acceptance
**Not yet accepted.** Local and CI results, plus resolution of object-identity and temporary-file cleanup concerns, are required before closing E2.
