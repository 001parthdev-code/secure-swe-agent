# A5 — Supervised local Git broker

Scope: local branch creation, explicit staging of one tracked file, diff review, SHA-256 approval, local commit. No push, remote operations, merge, force operations, or shell interpolation.

The broker is an **operator-side tool**, not a new permission for Qwen to execute arbitrary Git commands. It is suitable for a trusted disposable repository. Git config, filters, external helpers, and repository content remain outside the Enforcer security boundary; do not use this as a sandbox for hostile repositories.

Invariants: start on clean `main`/`master`; branch name `agent/task-*`; commit only on task branches; one tracked regular file per approval; staged diff fingerprint must match explicit approval; no unstaged modifications to the approved file; Git hooks disabled for broker commands. A5 does not certify that tests passed. Operators should inspect the diff and test results before approving.

Tested with disposable Git repositories on the development platform; GitHub CI still required. Next: A6 separate explicit approval for push and PR creation, with credential separation.
