# ADR-003 — Eight-crate Rust workspace

Status: Approved architecture; migration verification pending.

## Decision
Extract the existing Enforcer into eight crates: core, protocol, fs, isolation, transaction, execution, audit, cli. No new capability is enabled. Empty crates explicitly represent future responsibilities, not security controls.

## Assumptions and hypothesis
The source snapshot plus subsequent E2 patches represents the most recent available baseline. Separating modules without altering their operational logic should preserve observable request/response behavior. This must be verified rather than assumed.

## Boundaries
- CLI owns transport and orchestration.
- Core owns policy, depending on protocol and filesystem APIs.
- Filesystem owns OS-specific handle-relative operations; its public functions are low-level primitives and MUST NOT be exposed directly to an untrusted caller.
- Transaction crate contains a state machine only; no atomic commit guarantee.
- Isolation, execution and audit crates are placeholders, not functioning controls.

## Security caveat
This migration alone does not enforce the desired no-bypass architecture. Future work must introduce a capability-gated filesystem facade and prevent direct invocation of low-level operations by untrusted code.

## Evidence
No Rust toolchain was available in the artifact-building environment. Compilation, tests, Clippy, and cross-platform CI are pending.
