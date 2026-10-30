# UI-9: first live vertical slice (read-only)

This patch replaces mock task generation with a real local API invoking `agent/main.py --propose`, Qwen via Ollama, and approved read-only access through the existing Rust Enforcer. It intentionally does **not** connect apply, commit, publish, or recovery. Buttons for those operations are not displayed in live mode. The frontend is not ready for Hugging Face Spaces or internet exposure.

## Linux setup

Use a **fresh disposable Git repository** containing the buggy calculator fixture at `workspace/calculator/calculator.py`. Build the existing Enforcer (no changes). Ensure Ollama is reachable from Linux, with `qwen3.5:4b` available; if Ollama runs on Windows, configure an authorized private connection first.

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -r agent/requirements-live.txt
export SWE_DEMO_REPO="$HOME/secure-swe-agent/a7-demo"
export SWE_ENFORCER_BINARY="$HOME/secure-swe-agent/enforcer/target/debug/enforcer-cli"
export SWE_API_TOKEN="$(python3 -c 'import secrets;print(secrets.token_urlsafe(32))')"
export SWE_UI_ORIGIN='http://127.0.0.1:5173'
python3 -m agent.secure_swe_agent.live_api
```

Keep the API bound to 127.0.0.1. From Windows, establish an SSH local forward for API access, e.g. `ssh -L 8765:127.0.0.1:8765 samskara` (port-forwarding details depend on your VM configuration). Configure `ui/.env.local` with `VITE_SWE_OPERATOR_TOKEN` matching the Linux token. Do not commit either value. Start the UI on Windows using `npm run dev` and browse to `http://127.0.0.1:5173`. Vite proxies `/api` to the forwarded local backend.

**Security limitations:** The token is compiled into browser JavaScript and is only suitable for a private, single-user local demo. It is not an authentication solution for public hosting. The backend holds task state in memory and cannot resume a running proposal after restart. The trusted fixture is not a sandbox for hostile repositories. The model's output is untrusted and validated before display. The UI does not apply any file changes.

## Next increment

Connect the durable A7 journal and the three approval operations behind server-side authorization, then add persistent task status, recovery and integration tests. Never expose raw Enforcer, Git, or GitHub credentials to the browser. The Enforcer is frozen.
