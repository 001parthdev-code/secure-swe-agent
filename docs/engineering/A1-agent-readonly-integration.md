# A1 — Read-only agent integration

## Decision

Use local Qwen 3.5 4B via Ollama JSON responses, Python standard-library client, and a persistent Rust Enforcer process. Keep the existing `read_file` protocol unchanged.

## Invariants

- Model output cannot invoke arbitrary subprocesses or mutate files.
- Only operator-approved paths are eligible for Enforcer reads.
- The Enforcer retains final path authorization.
- Agent execution has a bounded number of steps; Enforcer replies have a timeout.
- Environment variables that enable prototype E2/E3 capabilities are removed from the spawned Enforcer environment.

## Limitations and next steps

A1 does not discover files, edit code, run tests, commit, or push. Later A2 adds controlled discovery; A3 introduces explicit human-approved writes; Git operations require a trusted broker and approval. No hostile-agent isolation claim is made.
