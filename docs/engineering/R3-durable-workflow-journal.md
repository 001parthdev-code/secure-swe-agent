# R3.1 — Durable workflow journal

## Scope

Introduces `agent/secure_swe_agent/workflow_state.py`, a SQLite-backed state journal with optimistic revision checks, atomic event recording, and restart reconciliation. This is an additive foundation; A7's CLI is **not yet wired** to the journal. Do not claim durable A7 recovery until R3.2 integration is verified.

## Invariants

- One task ID identifies one trusted repository and proposal digest.
- Each transition requires the current revision and an allowed state edge.
- Sensitive in-flight states require an approval digest and operation identifier. The coordinator remains responsible for verifying that the digest matches the exact reviewed action.
- Restart marks in-flight external side effects `needs_reconciliation`; it never repeats a write, commit, push, or PR creation automatically.
- A transition and its event are committed atomically.
- The database belongs outside the agent-writable workspace and must be restricted to the trusted operator.

## Remaining integration work

R3.2 will connect A7 prepare/apply/commit/publish operations to this store, define external-effect reconciliation (filesystem/Git/GitHub), enforce task-scoped approvals, and add subprocess-crash and retry integration tests. A persistent journal is not itself a security boundary or a complete distributed transaction mechanism.
