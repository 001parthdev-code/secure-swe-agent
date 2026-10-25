# M1 — Behavior-preserving modularization

## Problem
Single-crate layout couples policy, protocol, OS-specific filesystem operations, and CLI.

## Hypothesis
Extracting source into eight independently named crates without changing policy semantics preserves E1 and the fail-closed E2 modification behavior.

## Changes
Created a root Cargo workspace; extracted protocol, policy, filesystem, and transaction state machine; relocated CLI and adversarial tests; reserved isolation, execution, and audit crates; updated CI.

## Verification pending
Run `cargo generate-lockfile`, `cargo fmt --all`, `cargo test --workspace --locked`, `cargo clippy --workspace --all-targets --locked -- -D warnings` and Windows/Ubuntu CI. Compare protocol outputs and E1/E2 tests against previous baseline.

## Limitation
This is structural migration, not E2 isolation or transactional commit implementation. Do not enable `modify_file`.
