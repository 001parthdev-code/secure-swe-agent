# Secure SWE Agent — Operations, Verification and Next Decisions

_Last updated: 2026-10-26._

## Developer verification

From the repository root on Windows or Linux:

```sh
python -m unittest discover -s agent/tests -v
python -m compileall -q agent
```

The compilation command is quiet on success. Unit tests do not prove the Linux-only Enforcer modification path, remote GitHub publishing, or secure crash recovery.

Existing Rust Enforcer verification may be run without changing the frozen subsystem:

```sh
cd enforcer
cargo fmt --all -- --check
cargo test --workspace --locked
cargo clippy --workspace --all-targets --locked -- -D warnings
```

Use the repository's existing CI workflows for Linux integration. Preserve exact CI logs and commit IDs as release evidence.

## Reproducible demo requirements

- Dedicated disposable Git repository containing the intentionally buggy calculator and its six regression tests.
- Approved file catalog and proposal that match the exact source SHA-256.
- Working local Qwen/Ollama model and agent environment.
- Linux Enforcer binary built from the frozen workspace.
- Operator-controlled trusted-exclusive test workspace; not a hostile repository.
- GitHub demo repository with a baseline default branch, task-branch push authorization and scoped API token.
- Explicit approvals for modification, commit and publication.

**Demo outcome previously observed:** `agent/task-fix-subtraction`, commit `e782201c2d0b74772e1a741d8b3f3120b3228ba0`, PR https://github.com/001parthdev-code/secure-swe-agent-demo/pull/1.

Do not reuse an already-fixed fixture when claiming to demonstrate bug discovery and correction. Use a clean baseline for each run.

## Secrets and access

- Do not store `GH_TOKEN`, SSH private keys, passwords or credentials in the repository, model context, UI, screenshots or logs.
- Limit GitHub tokens to the demo repository and necessary Contents/Pull requests permissions.
- Preserve the broker's destination and fingerprint checks; never place a token in the Git remote URL.
- The repository is intended to retain exclusive commercial control. Confirm the legal copyright holder, license terms and contributor ownership before external contributions.

## Remaining engineering gates

| Gate | Must be established before calling it complete |
| --- | --- |
| R4 Security review | Document trust boundaries, risks, mitigations and explicit accepted prototype limitations |
| R5 Tests/CI | Reproducible cross-platform unit tests, Linux integration, negative authorization and fault-injection evidence |
| R6 API | Authenticated task creation, state retrieval, immutable review/approve actions, errors, events, and authorization tests |
| R7 Release | Setup instructions, deployment/runbook, CI evidence, versioned limitations, clean repository |
| Hosted UI | Browser task-to-PR demo against controlled Linux backend; no CLI steps required of evaluator |

## Decision log

- Keep the agent and Enforcer in **one** `secure-swe-agent` repository, with distinct `agent/` and `enforcer/` subtrees.
- Keep the Rust Enforcer **frozen** until the user explicitly authorizes production-grade security work.
- Preserve human approval at modification, commit and GitHub publication checkpoints.
- Use Qwen 3.5 4B via local Ollama for the prototype; no paid inference API required for the verified demo.
- Prioritize robust backend stabilization (R4–R7) before UI integration.
- Consider Hugging Face Spaces for the frontend and a separately controlled Linux backend; hosting is not yet implemented.

## Outstanding documentation questions

- What is the final release tag and exact Git commit containing the latest R3.4.4 changes?
- What are the actual CI job names and captured artifacts for the final backend release?
- Who is the legally correct copyright holder for code contributed by multiple people?
- Which Linux backend deployment and authentication method will be selected?
- What security guarantees, if any, will be claimed publicly beyond the trusted-fixture prototype?
