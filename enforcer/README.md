# Rust Enforcer — Secure SWE Agent subsystem

This directory is an independently buildable Rust Cargo workspace containing the eight Enforcer crates, integration harnesses, and engineering documentation. It remains part of the **Secure SWE Agent** repository.

## Build and verify

From this directory:

```sh
cargo fmt --all -- --check
cargo test --workspace --locked
cargo clippy --workspace --all-targets --locked -- -D warnings
cargo build --locked -p enforcer-cli
```

On Linux, the privileged security and integration harnesses live in `scripts/` and are run by GitHub Actions from this directory. Do not run privileged verification scripts on an untrusted host.

## Boundaries

E1–E4 are functional prototype capabilities. General-purpose agent execution, complete sandbox confinement, durable auditing, and hostile-writer transaction guarantees are **not** established. Windows sandbox work is frozen. See `../SECURITY.md` and `docs/`.
