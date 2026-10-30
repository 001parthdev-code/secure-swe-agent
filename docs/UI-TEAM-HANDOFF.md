# UI team handoff — Secure SWE Agent

## Objective
Build the user-facing interface for the existing supervised coding workflow. The Enforcer is frozen. The backend and its approval policies are owned by the core team.

## Directory ownership
- UI team: `ui/**` only.
- Core team: `agent/**`, `enforcer/**`, API implementation, authentication, GitHub integration, CI policies.
- Changes outside `ui/**` require separate approval and review.

## Acceptance criteria
1. A user can enter a task and see an explicit current status.
2. File changes appear in a readable diff with clear file paths.
3. Approve/reject actions require deliberate user interaction and display the resulting status.
4. Tests show real backend-reported results after integration; mock data must always be labeled.
5. Git publication requires a separate confirmation screen with repo, branch, commit and target branch.
6. Error, loading, empty, denied, stale-revision, and reconciliation states are represented.
7. Responsive layout, keyboard navigation, semantic controls, and accessible contrast.
8. No GitHub tokens, SSH keys, model prompts, or Enforcer commands in browser code.

## Backend contract
`ui/src/contracts.ts` defines a provisional `WorkflowApi` interface. It is a frontend contract **proposal**, not a claim that backend endpoints exist. The core team will finalize endpoint routes, auth/session behavior, and durable state transitions during R6.

## Approval invariant
The UI displays a specific immutable proposal. A click sends task ID and expected revision to the backend; the backend must bind the approval to the exact server-side digest and recheck it before side effects. Never trust a digest or authorization decision supplied solely by the browser.

## Git workflow
Use `feature/ui-*` branches. Submit PRs; do not push to `master`. Core team reviews dependencies, network access, browser security, API boundaries, and accessibility before merging.

## Hosting
The frontend is designed to be portable to a static deployment or Hugging Face Spaces Docker/static hosting, subject to hosting configuration. Production backend authentication, CORS, and network connectivity are not yet configured.

## Current limits
The workspace is an interactive mock. It cannot inspect real repositories, modify files, run tests, commit, or publish. The reference PR is historic demonstration evidence, not an action performed by this frontend.
