# R3.4.3 — Operator quarantine and GitHub reconciliation evidence

## Scope

This increment introduces two narrowly scoped primitives:

1. `WorkflowStore.quarantine_abandoned_owner`: atomic owner removal and uncertain-state journaling, **only after** a trusted operator independently confirms that the previous coordinator and its descendants have stopped. Lease expiration alone is not evidence. The method does not establish termination itself and never replays an operation.
2. `github_evidence`: read-only comparison of the approved branch/commit and matching open PR via the existing GitHub broker. Missing branches/PRs and conflicts remain uncertain; this function does not authorize continuation or modify workflow state.

## Invariants and assumptions

- Only a trusted operator invokes quarantine; `confirmed_stopped=True` is an assertion, not machine-verifiable proof. Do not expose this boolean to an untrusted API caller.
- The SQLite journal, proposal artifacts, Git config, and repo are operator-controlled. These primitives are **not** safe against malicious local writers.
- Owner/fence match is required, and the transition plus owner deletion is one SQLite transaction.
- No automatic retry, no PR creation, no branch push, and no transition from `needs_reconciliation` to a success state occurs here.
- GitHub evidence uses the configured origin validation and current broker lookups. It assumes trusted Git configuration and valid scoped API credentials. A remote observation is not atomic with future changes.

## Verification

Run `python -m unittest discover -s agent/tests -v` and `python -m compileall -q agent`.

Regression tests cover stale/expired ownership, wrong fencing, atomic quarantine after a simulated restart, no automatic reacquisition, matching remote evidence, and remote commit conflicts. Full suite in the patch assembly: 68 tests passed.

## Remaining work (not claimed complete)

- OS-backed coordinator/descendant termination verification, or an explicitly supervised shutdown protocol.
- End-to-end real process kill/crash tests, including failure between external side effect and SQLite commit.
- Durable capture of exact publication intent and external evidence provenance, and a reviewed reconciliation transition mechanism.
- Wiring recovery commands into the active durable CLI with strong operator authorization.
- Git transport configuration hardening and remote/API concurrency protection.

Do not describe R3.4 as production-grade crash recovery based on this increment alone.
