# R1/R2 — Stabilization increment 1

## Scope
- Remove temporary module-import debugging from the trusted calculator verification runner while preserving fresh-directory execution and the `-B` option.
- Make local Git commit review idempotent when exactly the approved tracked file is already staged. Reject unrelated staged files and unstaged drift.
- Validate the configured credential-free HTTPS GitHub origin without `insteadOf` transport rewriting; reject embedded credentials and malformed path shapes.
- Add regression tests for repeated review, unstaged drift, Git URL rewriting, and credential-bearing remotes.

## Assumptions and boundaries
- The Git repository and Git configuration remain **trusted/operator-controlled**. This patch does not make Git invocation safe for hostile repositories or hostile global Git configuration. In particular, Git transport rewrites still need an explicit effective-destination policy before production deployment.
- A4 verification executes only trusted calculator fixture code. A fresh temporary directory is not a sandbox.
- No network publishing or agent execution privileges were expanded.

## Follow-up
- Durable A7 workflow state, explicit idempotency keys, post-push PR recovery, and hardened Git execution environment belong to later stabilization increments.
