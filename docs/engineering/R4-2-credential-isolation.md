# R4.2 — Git subprocess credential isolation

## Finding
The A5 Git subprocess wrapper inherited the full operator environment, including GitHub API and local API tokens. Repository hooks are disabled, but Git subprocesses and configured helpers should not receive unrelated operator secrets.

## Change
The Git wrapper removes `GH_TOKEN`, `GITHUB_TOKEN`, and `SWE_API_TOKEN` from child environments. The A6 push path already removes `GH_TOKEN`; additional transport-level credential hardening and operator-controlled Git configuration remain explicit assumptions.

## Limits
This is not a general-purpose secret scrubber or a defense against malicious operator Git configuration. Test with a trusted disposable repository. No changes to the frozen Rust Enforcer.
