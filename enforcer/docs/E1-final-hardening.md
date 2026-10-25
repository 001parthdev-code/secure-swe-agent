# E1 final hardening — candidate release

## Scope and baseline
Based on the uploaded repository snapshot (`secure-swe-agent-master(1).zip`). This patch is **incremental**, not a full-project replacement.

## Assumptions
- An untrusted requester controls JSON requests and requested relative paths.
- The workspace directory is trusted at startup; the parent directory and host privileges are outside E1's security guarantees.
- Windows 10/11 and Linux 5.6+ are supported. Unsupported kernels/platforms must fail closed.
- The Enforcer runs without elevated privileges and cannot protect against an attacker who controls its process or kernel.

## Hypotheses
1. Windows component-by-component `NtCreateFile` traversal, using a retained directory handle and rejecting reparse points for **every** opened component, prevents intermediate junction traversal.
2. Linux `openat2` with `RESOLVE_BENEATH | RESOLVE_NO_SYMLINKS | RESOLVE_NO_MAGICLINKS` rejects traversal and symlink races.
3. A bounded JSON-lines reader that drains overlong lines maintains framing synchronization.

## Changes
- Windows: replaced one-shot multi-component NT open with single-component handle-relative traversal; opened intermediate directories with directory-only semantics; checked reparse attributes on each opened handle; rejected ADS syntax and ambiguous trailing spaces/dots.
- Protocol: corrected the oversized-line detection threshold to account for a full 64 KiB payload plus CRLF and the extra byte needed to detect overflow.
- Tests: added Windows ambiguous-component cases and CRLF oversized-payload regression.

## Verification record
- Prior snapshot: Windows and Ubuntu CI reported passing by the user for Iteration 5.
- This patch: **NOT compiled or executed in the authoring environment**. Windows and Linux CI results are pending.
- Security review remains necessary for NT native API behavior on target Windows versions, filesystem-specific reparse behavior, and stress testing under concurrent replacement.

## Acceptance gate
E1 may be closed only after: `cargo fmt --check`, `cargo test --locked`, `cargo clippy --locked --all-targets -- -D warnings` pass on Windows and Linux; Windows junction fixtures demonstrably execute; and remaining native-API assumptions are reviewed. A green test suite is evidence, not a proof of complete filesystem isolation.

## Known limitations
- Workspace-root canonicalization and initial opening are separate operations. Secure provisioning and startup ownership of the workspace are deployment assumptions.
- Existing Windows root-rename test conditionally does not exercise its assertion if the OS refuses the rename; it is not counted as positive evidence in that case.
- Windows junction and race testing is not exhaustive across filesystem drivers.
