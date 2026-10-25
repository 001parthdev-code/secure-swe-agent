# A4 — Controlled calculator verification

This increment verifies the functional flow: a failing trusted calculator fixture, an explicitly approved A3.2 E2 modification, and passing tests afterward.

**Trust boundary:** the Python verification runner is a CI/operator-owned harness, **not** an Enforcer tool. It executes Python test code with the runner identity. It must only be used with a disposable, operator-controlled fixture; do not point it at arbitrary agent-provided repositories. The existing E3 Enforcer command allowlist is unchanged.

**Deferred:** a genuinely isolated, general-purpose Enforcer test-running capability with process-tree termination, output/resource bounds, and filesystem confinement. This is necessary before arbitrary agent-authored tests can run.

The current verification result is a test report, not an isolation attestation.
