# ADR-007 — Windows restricted-token negative-write experiment

Status: experimental; production isolation remains **Unverified**.

## Problem and hypothesis

The Enforcer must demonstrate that a child process cannot mutate a protected directory through direct Windows filesystem APIs. A DACL existence check is insufficient. Hypothesis: an inherited-DACL-free directory granting access solely to the trusted user SID, paired with a child token restricted to the Builtin Users SID, causes Windows to deny the child a new-file create while the trusted process can write.

## Implementation

The disposable PowerShell fixture removes inherited access rules and grants full control only to the current trusted user SID. A Rust harness creates a restricted primary token with `CreateRestrictedToken`, disables privileges, and launches a Rust write probe using `CreateProcessWithTokenW`. The harness requires the probe to report `PermissionDenied`, checks the exit status, and verifies the unauthorized file is absent. No handles are explicitly inherited through this API.

## Threat assumptions and limitations

- This is a **single-operation, disposable-workspace experiment**, not a production DACL provisioner or an attestation.
- The CI account must possess the Windows privileges needed to call `CreateProcessWithTokenW`. If not, the test fails closed and the deployment design must be revisited; do not skip the test.
- A Windows administrator, SYSTEM, or other process able to rewrite the directory security descriptor is outside this narrow experiment.
- It does not yet prove isolation against alternate paths, inherited existing writable handles, token impersonation, child privilege escalation, or every filesystem type.
- Versioned modification remains disabled until isolation and transactional commits are separately verified.

## Acceptance

Trusted control write succeeds; restricted child reports access denied; target does not exist; Windows CI job passes. Record the actual job outcome before making any security claim.
