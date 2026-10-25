# R3.4 Increment 1 — Journal-first preparation and proposal evidence

## Scope

This increment adds a `preparing` journal state before branch creation, snapshots the exact proposal bytes into a task-ID-named artifact beside the operator-owned SQLite database, and requires that the supplied proposal still matches the snapshot before the E2 apply operation. The state journal now treats interrupted preparation as requiring reconciliation, without automatic replay.

## Assumptions and trust boundary

- The journal and its `.artifacts` sibling directory are trusted-operator-controlled and inaccessible to agent-generated code. This is an operational requirement, not independently enforced by SQLite.
- The A7 demo remains restricted to its trusted calculator fixture.
- The journal is not a filesystem, Git, or GitHub transaction coordinator.

## Evidence

Tests cover journal-before-side-effect ordering, interrupted preparation, proposal artifact persistence and tampering, restart recovery, and existing R3.1–R3.3 behavior.

## Known gaps — do not declare R3.4 complete

- No cross-process lease prevents two independent coordinators from performing different operations concurrently on the same repository.
- Proposal artifact storage is not hardened against malicious local filesystem actors or power-loss durability of its parent directory.
- Reconciliation does not yet inspect external filesystem, Git, or GitHub evidence or safely resolve uncertain operations.
- Existing legacy workflows created before this increment do not have proposal artifacts and cannot be applied through the revised durable adapter without migration.
- Active CLI needs an explicit reconciliation interface and an operator-controlled state-directory permission policy.

## Follow-up

Implement cross-process operation ownership and read-only evidence inspection, followed by a manual reconciliation decision procedure and fault-injection tests. Do not auto-retry external effects.
