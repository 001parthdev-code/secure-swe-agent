# A3.1 — Supervised code-change proposals

## Scope
The operator explicitly selects up to eight workspace-relative source files. The agent reads each through the existing Enforcer client, asks Qwen for complete replacement contents, and produces reviewable unified diffs and SHA-256 fingerprints of observed source contents.

## Security boundaries
- This increment **does not write files**, approve changes, run commands, or interact with Git.
- The Python agent must not access workspace files directly; observations come through the Enforcer.
- Model-selected paths are checked against the operator-approved set.
- The source digest is review metadata, **not** an E2 version token and does not authorize commits.
- Model output is untrusted. Proposed diffs require human review and later Enforcer-mediated version-checked application.
- No claim of Linux E2 integration is made by this increment.

## Next
A3.2: explicit approval and Linux-only E2 version-token application in a disposable workspace; fail closed on Windows. Add independent integration tests before enabling.
