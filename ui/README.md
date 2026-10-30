# Secure SWE Agent — Frontend workspace

React 18 + TypeScript + Vite. This is a **mock-only frontend**. It cannot execute the Enforcer, run tests, commit changes, or publish GitHub pull requests.

## Start

```powershell
cd ui
npm ci
npm run typecheck
npm run build
npm run dev
```

Open the local Vite URL (normally http://127.0.0.1:5173).

## What you can test

- Switch between Overview, Task activity, and Review & publish.
- Start or reset the supported calculator-subtraction demo.
- Inspect the proposed diff and view simulated test results.
- Review and confirm three simulated approval checkpoints (change, commit, publication).
- Reject a proposal and restart the simulation.
- Inspect activity events, task status, and the historical reference PR link.
- Resize the browser to test responsive layouts.

All simulated operations are labeled. Refreshing the page resets the in-memory mock state; persistence and real operations belong to the future backend.

## Integration boundary

`src/contracts.ts` defines the frontend `WorkflowApi`. `src/mockApi.ts` is an in-memory implementation. Replace it with a typed authenticated API adapter **only after** the backend contract is stable and tested. The backend—not the browser—must enforce approval fingerprints, revisions, authentication, repository restrictions, and authorization.

Keep `agent/` and `enforcer/` untouched. The Rust Enforcer is frozen.
