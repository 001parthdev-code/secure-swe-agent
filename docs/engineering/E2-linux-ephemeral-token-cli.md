# E2 Linux CLI prototype — ephemeral version tokens

## Scope
`get_file_version` issues a random, process-local token bound to a descriptor snapshot and exact relative path. `modify_file_versioned` consumes it once and calls the existing Linux atomic replacement backend.

## Deployment gate
By default modification is DENIED. Only a trusted operator may set `ENFORCER_TRUSTED_EXCLUSIVE_WORKSPACE=1`, and ONLY when all untrusted processes lack direct write/rename/unlink access to the workspace and its directories. This is a prototype integration gate, **not a sandbox attestation**. Do not enable it in hostile production.

## Limits
- Tokens expire on CLI restart and on subsequent observation of the same path.
- The token cache is bounded to 128 entries; cache clear invalidates older tokens.
- A successful rename may be followed by an fsync error: do not blindly retry.
- The existing atomic backend uses advisory locks, which do not stop hostile external writers.
- Metadata preservation, hostile rename races, durability and sandbox integration remain open.
- Windows stays disabled.

## Manual smoke test (trusted disposable workspace only)
1. Start one persistent `enforcer-cli` process with `ENFORCER_WORKSPACE` pointing to a disposable directory and `ENFORCER_TRUSTED_EXCLUSIVE_WORKSPACE=1`.
2. Create a regular file using `create_file`.
3. Call `get_file_version`, copy its `output`.
4. Call `modify_file_versioned` with that output as `expected_version`.
5. Confirm updated contents, and verify replay of the old token is denied.

## Acceptance
Rust formatting, tests, clippy, Ubuntu CI, and Linux end-to-end smoke test. This increment does not establish production security.
