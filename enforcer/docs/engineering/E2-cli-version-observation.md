# E2 CLI read-only version observation (increment)

## Scope
Adds `get_file_version` request to the existing CLI via `enforcer-core`. Linux-only.

## Invariants and limitations
- Workspace-relative normal path components only. Existing openat2-based filesystem resolution applies.
- Bounded 1 MiB read. Non-regular targets denied.
- Returned `observation-fnv64` value is NON-CRYPTOGRAPHIC and informational only. It MUST NOT be accepted as `expected_version` for a write.
- `modify_file_versioned` remains policy-denied. No change to Windows mutation behavior.
- Repeated reads do not prove race freedom. An attacker could mutate and restore contents.
- Future write API requires a cryptographically robust version commitment, entry-identity checks, and verified exclusive mutation authority.

## Acceptance
Run Cargo fmt, test, clippy on Windows; run same checks and Linux isolation job in Ubuntu CI.
No production security attestation is issued.
