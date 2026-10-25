# Linux V0.1 — Integrated functional release gate

## Scope
Single running `enforcer-cli` process: read, create, obtain process-local version token, reject invalid token, atomically modify a file, reject replay, deny arbitrary command, execute `true` and `false` as a dedicated non-root child, reject traversal, and produce ordered JSONL audit events. The integration test uses a disposable workspace and runs under a privileged CI supervisor **only** to exercise credential dropping.

## Test invariants
- Invalid/replayed version tokens do not modify the target.
- Allowlist rejects `/bin/sh`.
- Fixed probes return the expected exit codes.
- Each request yields one JSON response and one ordered audit event.
- No file contents or version tokens are written to audit output.
- Unexpected results fail the CI job; no permissive fallback.

## Explicitly unverified
- `ENFORCER_TRUSTED_EXCLUSIVE_WORKSPACE=1` is an operator assertion, not OS-enforced exclusivity.
- Arbitrary agent code execution is not supported or sandboxed.
- Filesystem/mount/network confinement, descendant process cleanup, hostile concurrent writers, crash durability, and tamper-evident audit storage are not verified.
- Windows isolation is frozen.

**Release classification:** functional Linux V0.1 controlled prototype, not production security approval.
