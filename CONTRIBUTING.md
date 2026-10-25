# Contributing

Secure SWE Agent is a unified project; its current Rust Enforcer subsystem is security-sensitive experimental software. Future agent code will live in this repository and must use the Enforcer boundary. Changes should preserve fail-closed behavior and the separation between trusted Enforcer code and untrusted requests.

## Local checks

```bash
cargo fmt --all -- --check
cargo test --workspace --locked
cargo clippy --workspace --all-targets --locked -- -D warnings
```

For Linux-specific functionality, run the corresponding Linux GitHub Actions integration job. Passing Windows builds does not validate Linux-only paths.

## Pull request expectations

Describe the threat or functional requirement, changed invariants, test evidence, limitations, and any effects on protocol compatibility. Update `docs/engineering/` and architecture documentation when behavior or trust boundaries change. Avoid suppressing compiler warnings or weakening a security assertion solely to make CI green.

Do not submit secrets, credentials, private workspaces, or raw ProcMon traces. Windows research remains frozen unless deliberately reopened.
