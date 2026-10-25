# Secure SWE Agent

**An AI software-engineering agent project with a security-first Rust enforcement foundation.**

> **Current milestone:** v0.1.0 — Rust Enforcer Linux functional prototype. The autonomous agent is planned, not implemented. Not production-secure.

## Repository layout

- `enforcer/` — self-contained Rust Cargo workspace, tests, engineering logs, and verification scripts.
- `agent/` — reserved for the future AI agent (not implemented).
- `.github/workflows/` — CI executes Cargo and integration tests from `enforcer/`.
- `docs/` — system-level architecture and release overview.

Run Enforcer commands from `enforcer/` (for example, `cd enforcer`), or use `cargo --manifest-path enforcer/Cargo.toml ...` from the repository root.

## Overview

Secure SWE Agent is one repository and one evolving product. Its intended AI agent will plan software-engineering tasks and request operations through the Rust Enforcer, which mediates access to files and controlled execution. **The agent layer is not implemented in v0.1.0.** The currently working deliverable is the Enforcer subsystem, not a separate product or repository.

The v0.1.0 milestone demonstrates the Enforcer E1–E4 working together in a controlled Linux integration test. It is intended for development, learning, and security experimentation—not execution of arbitrary hostile code.

## Project roadmap and architecture

**Implemented now:** Rust Enforcer, including E1–E4 functional prototype. **Planned in this same repository:** agent planning/reasoning, code understanding, tool orchestration, feedback and verification. Production isolation hardening is a separate release gate.


```text
 Future Secure SWE Agent / current test client
             |
        JSON Lines requests
             v
      +--------------------+
      | enforcer-cli       |---- JSON Lines audit ---> stderr
      | framing + dispatch |
      +---------+----------+
                |
      +---------v----------+
      | enforcer-core      |
      | policy + routing   |
      +---+----------+-----+
          |          |
    +-----v-----+  +-v------------------+
    | enforcer-fs|  | enforcer-execution |
    | safe file  |  | fixed Linux probes |
    | operations |  +--------------------+
    +-----+------+ 
          |
    +-----v----------------+
    | enforcer-transaction |
    | Linux version/commit |
    +----------------------+

 enforcer-protocol: shared request/response types
 enforcer-isolation: preflight and experimental OS isolation checks
 enforcer-audit: structured event encoding
```

Crates are libraries unless explicitly built as executables. The Enforcer CLI and the restricted Linux probe processes are separate processes. See [architecture and status](docs/ARCHITECTURE.md).

## Current Enforcer capabilities (v0.1.0)

| Capability | Linux v0.1 | Windows |
| --- | --- | --- |
| Workspace-relative read/create/basic modification | Implemented and tested | Existing workspace tests |
| `get_file_version` | Process-local token | Denied |
| `modify_file_versioned` | Controlled prototype; operator-gated | Denied |
| `run_command` | `true` / `false` only; operator-gated | Denied |
| JSONL audit stream | stderr | stderr |
| General-purpose agent command sandbox | **Not supported** | **Not supported** |

**Security boundary:** `ENFORCER_TRUSTED_EXCLUSIVE_WORKSPACE=1` is an operator assertion, not proof of exclusive mutation authority. E3's fixed probes are not a general-purpose isolated execution environment. See [SECURITY.md](SECURITY.md).

## Quick start

Requirements: Rust toolchain supporting edition 2024 and Cargo. Linux is required for the complete E2/E3 controlled flow.

```bash
cd enforcer
cargo build --locked -p enforcer-cli
mkdir -p /tmp/enforcer-demo
printf 'hello\n' > /tmp/enforcer-demo/example.txt
export ENFORCER_WORKSPACE=/tmp/enforcer-demo
printf '%s\n' '{"action":"read_file","path":"example.txt"}' | cargo run --quiet --locked -p enforcer-cli
```

Expected response (the audit event is separately written to stderr):

```json
{"status":"success","output":"hello\n"}
```

The CLI reads **one JSON object per line** on stdin and writes **one JSON result per line** on stdout. Keep the same CLI process alive when using version tokens, because tokens are process-local.

### Request examples

```json
{"action":"read_file","path":"example.txt"}
{"action":"create_file","path":"new.txt","content":"hello"}
{"action":"get_file_version","path":"example.txt"}
{"action":"modify_file_versioned","path":"example.txt","content":"updated","expected_version":"ephemeral-v1:<token>"}
{"action":"run_command","command":"true"}
```

The last two operations are **disabled by default**. Only use the controlled integration harness to exercise their prototype gates; do not set the trusted-exclusive flag on a workspace accessible to untrusted writers. The fixed-command execution test requires a privileged supervisor solely to drop child credentials.

## Build and verification of the Enforcer milestone

```bash
cargo fmt --all -- --check
cargo test --workspace --locked
cargo clippy --workspace --all-targets --locked -- -D warnings
```

Linux-only integrated verification is executed by the [Linux V0.1 GitHub Actions workflow](.github/workflows/enforcer-linux-v01-integration.yml) using a disposable workspace. The script is at [`enforcer/scripts/verify-linux-v01-integrated.py`](enforcer/scripts/verify-linux-v01-integrated.py); it requires a controlled privileged CI environment and is **not** a production isolation attestation.

## Repository map (current implementation)

| Location | Responsibility |
| --- | --- |
| `enforcer/crates/enforcer-cli` | JSONL framing, dispatch and audit emission |
| `enforcer/crates/enforcer-protocol` | Request/result contracts |
| `enforcer/crates/enforcer-core` | Policy, authorization and operation routing |
| `enforcer/crates/enforcer-fs` | OS-specific filesystem access |
| `enforcer/crates/enforcer-transaction` | Linux snapshots and atomic replacement prototype |
| `enforcer/crates/enforcer-execution` | Linux fixed-command restricted child |
| `enforcer/crates/enforcer-isolation` | OS preflight and experimental isolation tests |
| `enforcer/crates/enforcer-audit` | Structured audit events |
| `docs/` | Architecture decisions, experiments, engineering records |
| `enforcer/scripts/` | Integration and security test harnesses |

## Release scope and next steps

**v0.1.0:** functional Linux prototype, with E1–E4 integrated CI evidence. **Not production approved.** Next: isolate general-purpose execution, enforce workspace mutation authority, add process-tree/resource controls, improve durability and audit storage, and conduct adversarial validation. Windows sandbox research remains frozen.

Read [release notes](docs/releases/v0.1.0.md), [documentation index](docs/README.md), and [security limitations](SECURITY.md) before extending or deploying the system.

## Unified project roadmap

1. **v0.1.0 — Enforcer functional prototype (current):** integrated Linux E1–E4, with known security limitations.
2. **Enforcer security hardening:** enforce isolation and exclusive mutation authority, expand adversarial tests, improve process-tree controls and audit durability.
3. **Agent implementation in this repository:** add planning, code understanding, tool selection and verification components.
4. **End-to-end Secure SWE Agent:** connect the agent to the Enforcer through an explicit trust boundary and verify realistic software-engineering workflows.

The Enforcer remains modular and reusable, but it is **not being spun out into a separate repository or treated as the final product**.
