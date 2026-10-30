# LIVE-2: Controlled browser approval (increment 1)

Scope: operator-only, localhost FastAPI, fixed calculator fixture on Linux. This increment does not implement Git commits, publishing, or durable web-task recovery. The Rust Enforcer is unchanged.

## Contract

- `POST /api/tasks`: Qwen generates one proposal for `calculator/calculator.py`; no write.
- `GET /api/tasks/current`: returns the proposal's `proposal_sha256`, revision, and untrusted diff.
- `POST /api/tasks/{id}/approve`: requires `X-Operator-Token`, JSON `{ "revision": number, "proposal_sha256": "64 lowercase hex" }`; compares the exact stored bytes and task revision, marks the task applying before starting a worker. A duplicate or stale approval returns 409.
- `POST /api/tasks/{id}/reject`: requires token and `{ "revision": number }`; discards the pending proposal without modifying files.

The trusted A7 workflow creates a task branch from `main` or `master`, checks Git cleanliness, verifies the proposal's base hash and version token, requests the Enforcer's versioned modification, and runs the trusted calculator tests. The browser displays actual verification output. On unconfirmed outcomes the task enters `needs_reconciliation`; no automatic retry.

## Important limitations

- API task and proposal state are **in memory**. Restart loses pending approvals and task history. A crash during an external operation requires operator inspection of the disposable Git repository. This is **not** the durable R3 web coordinator.
- The existing `a7-demo` repository may already be on an `agent/task-*` branch or contain the fixed calculator. A new run requires a **fresh, clean, disposable** calculator repository on `main` with the original bug; do not reset or modify your main project.
- The API process must be a single trusted operator process, accessible only over loopback/SSH tunnel. Do not expose it to the internet or Hugging Face Spaces.
- The web UI cannot commit or publish yet. `approveCommit` and `approvePublish` deliberately remain unavailable.
- The proposal diff is untrusted model output; the user must review it before approving.
- Test fixtures and execution remain trusted-only; not a general-purpose sandbox.

## Validation

Run `python -m unittest discover -s agent/tests -v` and `python -m compileall -q agent`. On Windows run `cd ui; npm run typecheck; npm run build`. Then validate on Ubuntu with a fresh disposable repository, using the existing frozen Enforcer executable. Test rejection, stale approval, successful modification and test result, and no Git publication.
