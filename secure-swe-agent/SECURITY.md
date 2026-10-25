# Security status and reporting

## Current security status

**Secure SWE Agent v0.1.0 delivers only its Rust Enforcer subsystem as a controlled Linux functional prototype, not a production-secure sandbox.** Do not expose it to hostile multi-tenant workloads, untrusted arbitrary executables, or sensitive production repositories on the strength of the v0.1 tests alone.

- **E2:** Versioned atomic replacement has been exercised in a disposable Linux test. `ENFORCER_TRUSTED_EXCLUSIVE_WORKSPACE=1` asserts that the operator controls all writers; it does not enforce that claim. Hostile concurrent writers, crash durability and metadata preservation remain open.
- **E3:** Only fixed `true`/`false` probes are supported. A non-root UID/GID and `no_new_privs` do not constitute a complete filesystem/network/process sandbox. General-purpose command execution is unsupported.
- **E4:** Audit events are JSON Lines written to stderr, not durable or tamper-evident storage. An operator must collect and protect logs separately.
- **Windows:** The custom restricted-process experiments are frozen; Windows production isolation is not verified.
- **Linux isolation:** Existing credential and negative-write experiments demonstrate specific properties, not complete namespace, mount, network or process-tree confinement.

## Threat model boundary

The future agent will live in this repository but must remain across an explicit trust boundary from the Enforcer. Treat agent-generated requests, repository content, and executed code as untrusted. The trusted CLI/core must not be confused with the untrusted child process. A successful unit test, startup check, or single denied write does not certify the full security boundary.

## Reporting vulnerabilities

Avoid publicly posting exploit details against deployments you do not control. Contact the repository maintainer through the repository's private security reporting mechanism, if enabled; otherwise open a non-sensitive issue requesting a private contact channel. No dedicated security email address is asserted here.

## Production readiness blockers

1. Independently enforce exclusive workspace mutation authority and test hostile concurrent writers.
2. Establish verified filesystem, network and process confinement for general-purpose execution.
3. Enforce process-tree cleanup and CPU/memory/output limits.
4. Define crash recovery and durability semantics for commits.
5. Add protected, durable audit storage and security regression tests.
6. Complete a targeted security review and supported-platform matrix.
