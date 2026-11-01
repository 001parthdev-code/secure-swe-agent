# R5 — Complete Python agent CI gate

## Scope

This increment adds `.github/workflows/agent-release-ci.yml` without changing any files under `enforcer/`. It runs the complete discovered Python agent test suite on Ubuntu with Python 3.11 and 3.14, plus a Python compilation check.

The `fastapi`/`uvicorn` packages come from `agent/requirements-live.txt`; `httpx2` is installed explicitly because the current Starlette test client requires it. These are not locked dependencies; reproducible dependency pinning remains an R7 task.

## Validation

Locally, the uploaded baseline ran 85 Python tests successfully using the available Python interpreter. The new GitHub Actions workflow has **not** been executed in GitHub Actions yet; treat it as pending until both matrix jobs pass. The existing Enforcer workflows remain unchanged.

## Limits

These tests use mocks for GitHub and most browser operations. Green results do not demonstrate a real authenticated PR publication, malicious repository isolation, or complete crash recovery. The supported release scope remains the controlled CLI demonstration; React/FastAPI are experimental and suspended.

## Acceptance

1. Both Python versions install dependencies and complete the test suite.
2. No files under `enforcer/` change.
3. Existing Linux A3.2/A4 and Enforcer CI checks remain green.
4. Any failures are diagnosed and corrected before tagging v0.1.0.
