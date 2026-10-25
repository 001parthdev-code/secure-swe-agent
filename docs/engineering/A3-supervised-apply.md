# A3.2 — Supervised application through E2

## Design

The Qwen proposal remains untrusted data. The operator reviews the diff and obtains the SHA-256 digest of the complete proposal artifact. An explicit invocation with the same digest authorizes the exact artifact, not subsequent edits to it.

The apply process re-reads the current file through the Enforcer, compares it to the proposal's base SHA-256, obtains a process-local E2 version token, applies the replacement through `modify_file_versioned`, and re-reads the result.

## Invariants and limitations

- No direct Python workspace writes during application.
- Windows is proposal-only; apply is Linux-only.
- The trusted-exclusive flag is an operator assertion for a disposable, trusted workspace, **not** evidence of OS-enforced isolation.
- No model-controlled approval or automatic application.
- A3.2 accepts exactly one changed file per approval. Multi-file atomic transactions are not implemented.
- The fingerprint check and E2 snapshot check do not establish exclusive mutation authority against hostile writers.
- No arbitrary commands or Git pushes are enabled.
- Proposal inspection must be performed by the human before approving the digest; the digest alone does not prove review. The proposed diff is untrusted model output: inspect the **full replacement content** shown alongside it.

## Experiment

Run the Python unit tests on any platform. Run the Linux CI integration with a disposable workspace. It checks that an unapproved invocation leaves files unchanged and that an explicitly approved invocation commits through the Enforcer.
