# R3.4.4 — Operator recovery inspection and real-process crash tests

## Scope

Adds read-only inspection and evidence commands to the **durable operator CLI** and an explicitly operator-gated abandoned-owner quarantine command. Does not change the Rust Enforcer, A7 legacy CLI, security policy, or GitHub publishing broker.

## CLI commands

`python agent/a7_durable.py --db /trusted/state.sqlite recovery-inspect --id TASK`

`python agent/a7_durable.py --db /trusted/state.sqlite recovery-quarantine --id TASK --owner OWNER --fence FENCE --confirmed-stopped`

`python agent/a7_durable.py --db /trusted/state.sqlite recovery-filesystem --id TASK --relative workspace/calculator/calculator.py --expected-sha256 HASH`

`python agent/a7_durable.py --db /trusted/state.sqlite recovery-git --id TASK --expected-commit COMMIT`

`python agent/a7_durable.py --db /trusted/state.sqlite recovery-github --id TASK --github-repo OWNER/REPO --branch agent/task-NAME --expected-commit COMMIT --base main --title TITLE --body BODY`

The GitHub command requires `GH_TOKEN` in the operator process environment and makes read-only network queries.

## Invariants

- Quarantine requires independent operator verification that the prior coordinator **and descendants** cannot continue side effects. `--confirmed-stopped` is an assertion, **not** automated proof.
- Ownership expiry never authorizes takeover. Wrong fencing tokens are rejected.
- Evidence gathering is read-only and **does not transition** a task to success or authorize replay.
- Real OS-process termination tests use `os._exit` after acquiring ownership; they do not execute an external mutation or network publication.
- SQLite and immutable proposal artifacts must be stored outside any agent-writable directory.

## Remaining limitations / release gate

This increment **does not complete automatic recovery**. There is no independently verified process-liveness attestation, no atomic transaction spanning SQLite and Git/GitHub/filesystem, and no evidence-backed state-resolution action. After quarantine, a workflow remains `needs_reconciliation` and must not be resumed automatically. A production coordinator needs stronger process ownership (e.g. supervisor-owned process handles), fully specified resolution policy, and adversarial fault injection around actual side effects.

The Enforcer remains frozen.
