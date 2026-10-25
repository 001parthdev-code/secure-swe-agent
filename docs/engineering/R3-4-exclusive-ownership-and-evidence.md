# R3.4 Increment 2 — Cross-process ownership and read-only recovery evidence

## Purpose

Prevent two trusted coordinators from operating the same workflow concurrently and prevent an interrupted external operation from being replayed merely because a lease expired.

## Changes

- SQLite `operation_owners` table and atomic `BEGIN IMMEDIATE` acquisition, scoped to workflow ID.
- Ownership is exclusive across SQLite connections; only matching owner and fencing number can release it.
- `DurableA7.prepare` and side-effect wrapper `_run` acquire ownership before acting and release it after a recorded result.
- `recover()` does not mark a task as interrupted while it has an ownership record, even if the TTL expired. Expiry is **not proof** that the owner stopped.
- Read-only filesystem SHA-256 and Git HEAD evidence helpers for tasks already in `needs_reconciliation`.
- Fault-injection and cross-connection tests, including `KeyboardInterrupt`, stale ownership, and read-only evidence.

## Security and limitations

This is **not full evidence-based reconciliation**. Evidence helpers do not resolve journal state or authorize retries. They are valid only for trusted, operator-controlled repositories, not hostile concurrent writers. The Git evidence helper does not verify GitHub remote branches or pull requests. No automated lease takeover is provided: a crashed process may leave ownership requiring a future trusted recovery procedure. Do not expose the ownership or evidence APIs to an untrusted UI client.

The owner/fencing token is an application coordination mechanism, not an OS process sandbox or proof of exclusive filesystem authority. The SQLite database and proposal artifact directory must remain outside agent-writable paths. The legacy A7 CLI is not automatically upgraded to the durable adapter by this patch.

## Verification

`python -m unittest discover -s agent/tests -v`

`python -m compileall -q agent`

Cross-process ownership is tested through independent SQLite connections; real process termination and GitHub remote reconciliation are not yet verified.
