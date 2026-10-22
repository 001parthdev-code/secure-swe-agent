# ADR-004: Isolation verification must fail closed

Status: Accepted for the isolation preflight foundation; native sandbox provisioning remains pending.

## Threat model

An untrusted agent can submit arbitrary tool requests. Repository contents may be malicious. A hostile process may attempt direct writes or path substitution. A privileged host administrator and kernel compromise are outside the present boundary. Processes sharing the Enforcer's host identity are **not** isolated by ordinary directory mode bits.

## Hypothesis

A separate isolation crate that never conflates filesystem metadata inspection with verified exclusive mutation authority will prevent the transaction engine from accidentally enabling versioned modification on a weak deployment.

## Decision

`enforcer-isolation` exposes a read-only workspace inspection and a fail-closed `require_exclusive_mutation()` check. No current backend can issue a `Verified` result. The public API does not permit callers to forge an attestation. It does not change workspace permissions or execute privileged commands.

## Future implementation gates

- Linux: establish separate OS credentials and enforce mount/user namespace or equivalent sandbox boundaries; verify host paths and mutation attempts from the untrusted identity.
- Windows: establish separate process token/identity and explicit DACL restrictions; validate effective access and deny direct mutation from the untrusted token.
- Verify containment for files, directories, links, mounts, and concurrent replacement.
- Integrate the attestation with transaction initialization; do not enable `modify_file_versioned` before these gates pass.

## Known limitations

POSIX permission checks are advisory. Windows ACLs are not inspected yet. This patch **does not provide OS-enforced isolation**, and E2 remains incomplete.
