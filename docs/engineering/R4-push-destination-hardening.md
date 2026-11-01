# R4 — Git push destination validation

## Finding

The A6 publishing broker validates `remote.origin.url`, but Git uses `remote.origin.pushurl` when configured. A repository with an approved fetch URL and an alternate push URL could send an approved commit to an unintended destination.

## Correction

Reject an explicitly configured local `remote.origin.pushurl` during publishing-plan creation. This is a conservative restriction for the trusted-operator CLI prototype, not a complete defense against hostile Git configuration. The system still assumes trusted global/system Git configuration and a trusted repository, as documented by the broker.

## Tests

- Reject a different explicit push URL.
- Reject an explicit push URL even when it matches the expected repository, to keep the destination configuration unambiguous.
- Preserve existing GitHub origin and approval tests.

Local validation in the audit environment: 87 Python tests passed; `compileall -q agent` succeeded. No authenticated GitHub push was performed.

## Remaining release considerations

- Audit environment-controlled Git transport overrides (`GIT_CONFIG_*`, global `url.*.insteadOf`, `remote.*`), and document operator-controlled configuration requirements.
- Evaluate secret handling and network timeouts in CLI publishing.
- Verify CI and the controlled Linux A7 demonstration before release.
- The experimental browser API is not supported for the CLI-first v0.1.0 release.

The Rust Enforcer is frozen and unchanged.
