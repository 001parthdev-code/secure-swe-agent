# LIVE-3: supervised Git commit and GitHub publication

This increment extends the **local-only, trusted calculator** FastAPI gateway. It does not change the Rust Enforcer.

## State machine

After LIVE-2 verification, the UI requests a separate `review-commit`, inspects the staged diff, and explicitly approves the fingerprint and revision via `approve-commit`. The backend calls A7 `workflow.commit`, which reruns trusted verification and enforces the exact staged-diff fingerprint. It then exposes a distinct `review-publish` plan; the operator reviews repository, base, branch, commit, title and body before approving the exact publishing fingerprint via `approve-publish`. Existing A6/R2 recovery broker performs the push and PR creation. The frontend cannot choose the GitHub destination or send its own Git commands.

Endpoints (all require `X-Operator-Token`):

- `POST /api/tasks/{id}/review-commit`
- `POST /api/tasks/{id}/approve-commit` with `{revision, staged_sha256, message}`
- `POST /api/tasks/{id}/review-publish`
- `POST /api/tasks/{id}/approve-publish` with `{revision, approval_sha256}`

`SWE_GITHUB_REPO` must be set on the **Linux API process** to an operator-approved disposable GitHub repo (e.g. `owner/demo`), with `SWE_GITHUB_BASE=main` (default). Configure `origin` in the disposable Git repository to the exact credential-free HTTPS GitHub URL. The A6 broker requires `GH_TOKEN` in the Linux API environment to create a PR; Git push credentials must be separately configured through trusted Git configuration. Never put tokens in the React build or Vite `VITE_*` variables. The current one-command launcher does **not** automatically provision these publishing settings; operator setup is still required.

## Boundaries and limitations

- This is **not production-ready**: FastAPI task state is in memory, single-process only, and an interrupted commit or publish operation enters `needs_reconciliation`. It does not automatically retry uncertain external side effects. Do not expose this API to the internet.
- Existing A5/A6 broker security assumptions still apply: trusted operator-controlled repository and Git configuration, and a fixed approved calculator fixture.
- Use a **fresh disposable repository** on `main` containing the buggy calculator. LIVE-2's previous task branch cannot be reused as a new task baseline.
- Backend enforces exact proposal, staged diff, and publication-plan approvals. Tests mock external effects; they do not demonstrate a live GitHub PR.
- The Enforcer remains frozen.

## Local checks

```
python -m unittest discover -s agent/tests -v
python -m compileall -q agent
cd ui
npm run typecheck
npm run build
```

Do not merge until the browser-driven commit and PR have been tested on Ubuntu against a disposable GitHub repo with CI green.
