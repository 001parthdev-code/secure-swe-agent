# Secure SWE Agent — A1 Read-Only Prototype

This is the first **agent** implementation, using local Ollama (`qwen3.5:4b`) and the existing Rust Enforcer JSON-lines protocol.

## Supported

- User task -> bounded Qwen decision loop -> approved Enforcer `read_file` -> proposed plan.
- Explicit file allowlist supplied by the operator; no autonomous repository enumeration yet.
- No file writes, shell commands, Git operations, or automatic PRs.
- No third-party Python packages required.

## Setup (Windows PowerShell)

From the repository root, with Ollama running and `qwen3.5:4b` installed:

```powershell
cd enforcer
cargo build --locked -p enforcer-cli
cd ..
python agent/main.py "Explain this source file and propose one improvement" --workspace .\workspace --enforcer .\enforcer\target\debug\enforcer-cli.exe --file hello.txt
```

The model may request to read `hello.txt`, then return a plan. The exact Rust binary target name is `enforcer-cli`; check `enforcer/crates/enforcer-cli/Cargo.toml` if your local build differs.

For Linux, use `./enforcer/target/debug/enforcer-cli` instead.

## Tests

```powershell
python -m unittest discover -s agent/tests -v
```

## Security limits

This is a **read-only agent prototype**. The Enforcer is the authorization authority. The agent additionally restricts paths to the explicit allowlist; the model's tool decisions are not trusted. Untrusted source-file contents can still influence model reasoning; prompts are not a security boundary. No production sandbox certification is implied.
