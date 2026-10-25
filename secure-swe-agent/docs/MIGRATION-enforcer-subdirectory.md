# Enforcer subdirectory migration

The Enforcer Cargo workspace has moved from repository root into `enforcer/`. The agent remains in this same repository under `agent/` (planned).

- The repository root no longer contains a Cargo manifest. `enforcer/Cargo.toml` is the **only** Cargo workspace root.
- `Cargo.lock`, `crates/`, `scripts/`, and Enforcer engineering records moved under `enforcer/`.
- GitHub Actions checkout remains at repository root; all job commands run with `working-directory: enforcer`.
- Run `cd enforcer` before local Cargo commands.
- No Rust source code or security policy is intentionally modified by this migration.

## Verification

```sh
cd enforcer
cargo fmt --all -- --check
cargo test --workspace --locked
cargo clippy --workspace --all-targets --locked -- -D warnings
```

Linux-only runtime tests must be run in the appropriate privileged, disposable CI environment. This relocation is not a new security attestation.
