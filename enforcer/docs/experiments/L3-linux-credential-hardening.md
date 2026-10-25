# L3 Linux credential hardening — candidate

## Scope

Hardens the existing disposable negative-write experiment. The child now drops supplementary groups, sets real/effective/saved GID and UID to the untrusted identity, and enables `PR_SET_NO_NEW_PRIVS` before `exec`. The probe verifies real/effective identities, zero supplementary groups, and `PR_GET_NO_NEW_PRIVS == 1` before attempting creation. Failures are terminal.

## Threat addressed

A process with residual supplementary groups, saved privileged identity or ability to gain privilege through exec could bypass a UID-only boundary. The experiment now checks these specific preconditions.

## Not established

This is NOT full Linux sandboxing or an isolation attestation. It does not yet establish mount/user/pid namespaces, seccomp, descriptor hygiene, ACL safety, resource limits, confinement of subprocesses, or arbitrary path mutation denial. `modify_file_versioned` must remain disabled.

## Verification

Run `cargo fmt --all -- --check`, `cargo test --workspace --locked`, `cargo clippy --workspace --all-targets --locked -- -D warnings`, and privileged `bash scripts/verify-linux-isolation.sh` on Ubuntu CI. Confirm the existing negative-write experiment still passes. Record platform/kernel and results.

## Status

Implementation candidate; runtime evidence pending.
