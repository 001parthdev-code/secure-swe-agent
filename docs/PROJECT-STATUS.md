# Secure SWE Agent — Verified Status and Open Work

_Last updated: 2026-10-26. Documentation snapshot; not a production-security certification._

## Product definition

Secure SWE Agent is a supervised AI software-engineering system. Its Python agent uses a locally hosted Qwen model to inspect approved repository content, propose code changes, request operator approval, and coordinate verification and Git/GitHub publication. A separate Rust Enforcer mediates authorized filesystem operations and restricted execution. The Enforcer is a **frozen functional prototype** until a separately authorized production-security phase.

## Demonstrated end-to-end result

A disposable calculator repository was used to demonstrate the following chain:

1. Qwen proposed correcting `subtract(a, b)` from addition to subtraction.
2. The operator reviewed the proposed diff and authorized the exact proposal fingerprint.
3. The Linux Rust Enforcer applied the approved change using its E2 versioned modification path in a trusted disposable workspace.
4. Six calculator regression tests passed.
5. The supervised Git broker created commit `e782201c2d0b74772e1a741d8b3f3120b3228ba0` on `agent/task-fix-subtraction`.
6. The GitHub publishing broker returned `pull_request_created` for https://github.com/001parthdev-code/secure-swe-agent-demo/pull/1.

This proves the controlled demonstration path. It does **not** establish reliable autonomous performance across arbitrary repositories or production-safe execution of untrusted code.

## Component inventory

| Area | Current evidence | Qualification |
| --- | --- | --- |
| A1 model integration | Ollama + `qwen3.5:4b` local request and file-read demo succeeded | Model outputs remain untrusted |
| A2 repository analysis | Approved catalog selection and Enforcer reads demonstrated | No unrestricted repository enumeration |
| A3 proposals | Correct calculator diff and proposal fingerprint demonstrated | Human approval required |
| A3.2 apply | Linux E2 approved replacement succeeded | Trusted-exclusive workspace assumption |
| A4 verification | Six calculator tests passed after correction | Trusted fixture runner, **not a sandbox** |
| A5 Git | Approved local task-branch commit demonstrated | Operator-controlled repository |
| A6 GitHub | Live branch publication and PR creation succeeded | Credentialed operator-controlled broker |
| A7 orchestration | End-to-end supervised demo completed | Multiple CLI checkpoints; not yet a unified UI |
| R1–R2 stabilization | Code cleanup, staged-review and publishing recovery patches reported green | No full external security audit |
| R3 journal and recovery | SQLite journal, adapter, ownership/evidence, operator recovery and crash-test increments reported green | Recovery still has explicit manual reconciliation limits |
| Rust Enforcer | E1–E4 integrated functional Linux prototype | Frozen; not production hardened |
| Windows | Agent analysis/proposals work locally | Linux-only E2 versioned mutation not available on Windows |

## Known constraints and accepted prototype risks

- Enforcer E2 requires trusted exclusive workspace control; this is not a general hostile-writer guarantee.
- Enforcer E3 only supports fixed probes, not arbitrary build/test execution.
- A4 executes only operator-owned trusted fixtures. Do not point it at untrusted repository tests.
- Durable SQLite state is not an atomic transaction with filesystem changes, Git commits, or GitHub requests. Uncertain outcomes require evidence-backed reconciliation.
- Recovery quarantine relies on trusted operator confirmation; expiration alone does not prove a worker has terminated.
- Workflow approvals must bind to exact proposed content, staged diff, commit and publication destination. Do not replace them with UI-only confirmation.
- Public web access is not approved yet; authentication, authorization, isolation and deployment testing are outstanding.
- GitHub credentials and SSH keys must remain outside model prompts, repository content and frontend code.

## Frozen boundary

**Do not modify `enforcer/`** (source, Cargo files, protocol, tests, scripts or configuration) during R4–R7 or UI work. Use its current supported interface. Any incompatible feature must be constrained or deferred until the user explicitly initiates production-security hardening.

## Outstanding milestones

- **R4:** Agent-side security and deployment threat-model review; identify release blockers.
- **R5:** Adversarial and integration tests, including Linux CI and failure scenarios.
- **R6:** Durable, authenticated, UI-ready backend API; no direct frontend access to Enforcer or credentials.
- **R7:** Final documentation, reproducible Linux deployment, acceptance checklist and release evidence.
- **UI:** Hosted frontend (Hugging Face Spaces is under consideration) with a separately controlled Linux backend. Deployment design is **proposed, not implemented**.

## Evidence standard

A green unit-test suite is evidence for the tested assertions only. The latest R3.4.4 patch was reported green by the operator; it has not been demonstrated here as complete automatic crash recovery. Track test command, commit SHA, environment, and resulting log for each final release gate.
