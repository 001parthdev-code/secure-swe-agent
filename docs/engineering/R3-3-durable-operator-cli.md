# R3.3 — Durable A7 operator entrypoint (increment 1)

## Scope

Adds `agent/a7_durable.py` as an **opt-in** operator entrypoint that uses the R3.1 SQLite journal and R3.2 `DurableA7` adapter. The legacy `agent/a7_demo.py` remains unchanged. No Enforcer policies or GitHub permissions change.

## Invariants

- SQLite database must be in a trusted, operator-owned directory **outside** the agent workspace and repository under modification.
- `--id` and `--revision` identify the workflow and expected journal revision for mutating operations. A stale revision cannot trigger the side effect.
- `review-commit` and `review-publish` require the corresponding journal state.
- Before `apply`, `commit`, and `publish`, the adapter records an in-flight state. If an operation fails or its outcome is uncertain, it does not automatically retry.
- `recover --confirm-no-active-operations` is operator-only. Stop all coordinators before running it. Recovery marks interrupted operations as `needs_reconciliation`, not success.
- Approvals still bind to proposal/staged diff/publishing plan via the existing A3/A5/A6 brokers.

## Example (trusted Linux fixture only)

```bash
mkdir -p "$HOME/.local/state/secure-swe-agent"
python3 agent/a7_durable.py --db "$HOME/.local/state/secure-swe-agent/tasks.sqlite" prepare \
  --repo ./a7-demo --proposal ./proposal.json --slug fix-subtraction
python3 agent/a7_durable.py --db "$HOME/.local/state/secure-swe-agent/tasks.sqlite" status \
  --id WORKFLOW_ID
python3 agent/a7_durable.py --db "$HOME/.local/state/secure-swe-agent/tasks.sqlite" events \
  --id WORKFLOW_ID
```

The `prepare` response includes `workflow_id` and `revision`. Use these for the next operation; use the new revision returned by each completed operation. The CLI also offers `apply`, `review-commit`, `commit`, `review-publish`, `publish`, and `recover` (see `--help`).

## Known limitations — NOT a completed crash-recovery system

1. `prepare` still creates the Git branch **before** journaling the task. A crash in that interval can leave an unjournaled branch. This must be resolved before a general-purpose UI/API.
2. Reconciliation is **manual**. There is no automatic filesystem/Git/GitHub evidence comparison, and no automatic transition out of `needs_reconciliation`.
3. The confirmation flag for `recover` does not provide cross-process locking. Never run recovery while another coordinator is active.
4. The journal records a proposal digest but not durable proposal bytes or an immutable proposal artifact reference. Keep the reviewed proposal available and unchanged.
5. The current SQLite store assumes trusted single-host operation. It is not a security boundary and has no authentication or user/session isolation.
6. `apply` still relies on the Linux trusted-exclusive-workspace prototype; only trusted disposable fixtures are allowed.

## Verification

`python -m unittest discover -s agent/tests -v` — 56 tests passed in the assembled baseline. This tests CLI parsing, restart state, recovery gating, and no replay of uncertain operations; it is not a live GitHub integration test.

## Next

R3.4: journal-before-branch preparation, immutable proposal storage, cross-process operation leases, evidence-based reconciliation, and failure-injection integration tests. Then R4 security review.
