# Secure SWE Agent

**A supervised, local-model software engineering agent with a Rust security enforcement foundation.**

[![Rust](https://img.shields.io/badge/Rust-Enforcer-000000?logo=rust&logoColor=white)](https://www.rust-lang.org/)
[![Python](https://img.shields.io/badge/Python-Agent-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![Linux](https://img.shields.io/badge/Linux-Integrated-FCC624?logo=linux&logoColor=black)](https://www.kernel.org/)
![Status](https://img.shields.io/badge/status-supervised_prototype-orange)
![License](https://img.shields.io/badge/license-proprietary-red)

[![Rust CI](https://github.com/001parthdev-code/secure-swe-agent/actions/workflows/enforcer-ci.yml/badge.svg)](https://github.com/001parthdev-code/secure-swe-agent/actions/workflows/enforcer-ci.yml)
[![E2 Linux](https://github.com/001parthdev-code/secure-swe-agent/actions/workflows/enforcer-e2-linux.yml/badge.svg)](https://github.com/001parthdev-code/secure-swe-agent/actions/workflows/enforcer-e2-linux.yml)
[![E3 Linux](https://github.com/001parthdev-code/secure-swe-agent/actions/workflows/enforcer-e3-linux.yml/badge.svg)](https://github.com/001parthdev-code/secure-swe-agent/actions/workflows/enforcer-e3-linux.yml)
[![E4 Audit](https://github.com/001parthdev-code/secure-swe-agent/actions/workflows/enforcer-e4-audit.yml/badge.svg)](https://github.com/001parthdev-code/secure-swe-agent/actions/workflows/enforcer-e4-audit.yml)
[![Linux Integration](https://github.com/001parthdev-code/secure-swe-agent/actions/workflows/enforcer-linux-v01-integration.yml/badge.svg)](https://github.com/001parthdev-code/secure-swe-agent/actions/workflows/enforcer-linux-v01-integration.yml)

> **Release candidate (November 2026):** The supervised A1–A7 calculator-repair workflow has been demonstrated end to end, including a real GitHub pull request. R1–R3 stabilization and targeted R4 hardening are implemented; release-gate verification remains. The CLI is the supported prototype interface. React, FastAPI and the development launcher are retained as **experimental, suspended** components, not deployed services. The Rust Enforcer is frozen and is **not** a production-secure sandbox.

## What it does

Secure SWE Agent uses a locally hosted Qwen model to inspect an **operator-approved file catalog**, propose source changes, and coordinate a supervised coding workflow. Human approval is required before protected modification, Git commit, and GitHub publication. The Rust Enforcer mediates authorized file operations; separate trusted Python components handle controlled verification and Git/GitHub operations.

The current prototype is **not** an unattended coding service for arbitrary untrusted repositories.

## Demonstrated workflow

1. A user requests a calculator bug fix.
2. Qwen (`qwen3.5:4b` via Ollama) examines approved source and proposes a diff.
3. The operator reviews and approves the exact proposal fingerprint.
4. On Linux, the Rust Enforcer applies the approved version-checked modification in a trusted disposable workspace.
5. The operator-owned calculator regression suite passes **6/6 tests**.
6. The Git broker creates an approved commit on `agent/task-fix-subtraction`.
7. The GitHub broker pushes the task branch and creates a pull request after separate approval.

**Verified demonstration:** [Calculator subtraction fix — PR #1](https://github.com/001parthdev-code/secure-swe-agent-demo/pull/1) · commit `e782201c2d0b74772e1a741d8b3f3120b3228ba0`.

This proves the controlled demonstration path, **not** general-purpose autonomous repair reliability.

## Architecture

```text
Human operator
      |
      v
Python agent + supervised workflow (agent/)
      |-- Qwen 3.5 4B / Ollama: analysis and proposals
      |-- SQLite journal: task state, revisions and recovery evidence
      |-- Human approval: proposed edit / commit / publication
      |-- Enforcer client ---> Rust Enforcer (enforcer/; frozen)
      |                         |-- E1 filesystem operations
      |                         |-- E2 Linux versioned modification
      |                         |-- E3 fixed-command probes
      |                         `-- E4 structured audit events
      |-- Trusted calculator verifier (not a sandbox)
      |-- Trusted Git broker
      `-- GitHub publishing broker ---> approved task branch / PR
```

The model does **not** receive GitHub credentials or authorization authority. The experimental frontend must not be treated as an authorization boundary; privileged actions require backend validation.

See [current architecture and trust boundaries](docs/ARCHITECTURE-CURRENT.md).

## Repository layout

| Path | Purpose |
| --- | --- |
| [`agent/`](agent/) | Qwen integration, proposals, approval tools, A7 CLI, durable journal and recovery modules |
| [`enforcer/`](enforcer/) | Independently buildable eight-crate Rust Enforcer workspace; **frozen** |
| [`docs/`](docs/) | Architecture, project status, operations, engineering records |
| [`.github/workflows/`](.github/workflows/) | Automated verification and Linux integration jobs |
| `workspace/` | Local controlled example/benchmark fixtures |

The Enforcer and agent are **one project in one repository**, not separate products.

## Developer setup and checks

**Prerequisites:** Python, Git, Rust/Cargo, and Ollama with `qwen3.5:4b` for model-backed tasks. The complete Python test suite additionally requires `agent/requirements-live.txt` and `httpx2` (as installed in agent release CI). Linux is required for the demonstrated E2 versioned-apply path. The agent's core Python tests use the standard library; follow the individual scripts' help output for workflow-specific arguments.

From the repository root:

```bash
python -m pip install -r agent/requirements-live.txt httpx2
python -m unittest discover -s agent/tests -v
python -m compileall -q agent
```

Build and verify the **unchanged** Enforcer:

```bash
cd enforcer
cargo build --locked -p enforcer-cli
cargo fmt --all -- --check
cargo test --workspace --locked
cargo clippy --workspace --all-targets --locked -- -D warnings
```

For a basic local, read-only agent interaction, see [`agent/README.md`](agent/README.md) and `python agent/main.py --help`. For supervised A7 stages, use `python agent/a7_demo.py --help` (and each subcommand's `--help`). Durable operator tooling is available through `agent/a7_durable.py` but is **not** a fully automated crash-recovery service.

**Do not run the complete modification/publishing demo against your primary repository.** Use an approved disposable Linux workspace and a separate GitHub demonstration repository. See [operations and demo prerequisites](docs/OPERATIONS-AND-ROADMAP.md).

## Current capabilities and limits

| Area | Implemented / demonstrated | Important limitation |
| --- | --- | --- |
| A1–A2 | Local model integration, approved catalog selection, Enforcer-backed reads | Not unrestricted repository discovery |
| A3 | Diff proposals and supervised E2 application | Versioned apply demonstrated on Linux only |
| A4 | Trusted calculator regression verification | Not safe for arbitrary untrusted test code |
| A5–A6 | Approved local Git commits, task-branch push and GitHub PR | Requires operator-controlled repository and credentials |
| A7 | Complete supervised calculator-to-PR demonstration | CLI supported; browser integration experimental and suspended |
| R1–R2 | Verification and Git publishing stabilization | Not a general security certification |
| R3 | SQLite journal, ownership controls, recovery evidence and operator tooling | Uncertain external effects still require trusted reconciliation |
| Enforcer E1–E4 | Functional Linux integration | Not production-grade hostile-code isolation |

**Security limitations:** E2's `ENFORCER_TRUSTED_EXCLUSIVE_WORKSPACE=1` is an operator assertion, not independently verified exclusive authority. E3 supports only fixed probes, not arbitrary sandboxed test execution. SQLite transitions cannot atomically commit filesystem, Git or GitHub side effects. No public deployment is approved yet.

The **entire `enforcer/` tree is frozen** until production-security hardening is explicitly authorized. New agent and UI work must use its existing contract without bypassing its restrictions.

## Roadmap

- **R4:** Targeted agent-side security hardening implemented (push destination, credential filtering, commit-approval binding); residual risks documented.
- **R5:** Full Python CI and selected adversarial/fault-injection tests implemented; final release evidence still required.
- **R6/UI:** Experimental React/FastAPI/launcher retained but **suspended and unsupported** for v0.1.0.
- **R7:** Documentation prepared; final Linux verification, CI evidence, and release tagging pending.
- **Later, separately authorized:** Production-grade Enforcer hardening and broader execution isolation.

## Documentation

- [Verified project status](docs/PROJECT-STATUS.md)
- [Current architecture](docs/ARCHITECTURE-CURRENT.md)
- [Operations and roadmap](docs/OPERATIONS-AND-ROADMAP.md)
- [Security considerations](SECURITY.md)
- [Enforcer subsystem](enforcer/README.md)
- [Engineering records](docs/README.md)
- [Release checklist](docs/RELEASE-CHECKLIST-v0.1.0.md)
- [Changelog](CHANGELOG.md)

## License and commercial use

Secure SWE Agent source code is licensed under the **Apache License, Version 2.0**. See [LICENSE](LICENSE) and [NOTICE](NOTICE). The license permits use, modification, redistribution, and commercial use subject to its terms. Third-party dependencies and model weights retain their own applicable licenses; this license does not grant trademark rights or certify the software as production-secure.

---

*This README describes verified prototype functionality and documented engineering status. It does not claim production-security certification.*
