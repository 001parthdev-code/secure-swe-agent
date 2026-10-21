# E1 hardening iteration 2 — incremental patch

Apply the ZIP contents at the repository root. Only two Rust files change; `docs/` is new. No Cargo dependencies change.

Run from `enforcer/`:

```sh
cargo fmt
cargo fmt --check
cargo test
cargo clippy --all-targets -- -D warnings
```

**Important:** This patch adds a Windows junction test that may fail because the existing path checks are not a robust defense against reparse points. If it fails, preserve the test output and do not weaken the test. This is a security finding to fix in the next iteration. Rust tests have not been run in the patch-authoring environment.
