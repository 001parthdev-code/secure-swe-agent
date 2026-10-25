# Assumptions and trust boundaries

| ID | Assumption | Classification | Consequence if false |
|---|---|---|---|
| A-001 | The model/agent and its request strings are untrusted. | Design invariant | Enforcer must validate every request. |
| A-002 | The launcher sets `ENFORCER_WORKSPACE` to a trusted directory. | Deployment assumption | A compromised launcher can authorize an unintended root. |
| A-003 | The workspace can contain attacker-influenced paths. | Threat-model assumption | Path traversal, links, reparse points and races require defense. |
| A-004 | Cross-platform behavior differs for path interpretation and link handling. | Design assumption | OS-specific verification and implementations are required. |
| A-005 | E1 grants read-only file access; writes and commands remain denied. | Scope decision | New capabilities need independent authorization and isolation. |
| A-006 | A workspace directory is not concurrently mutated by a hostile actor during E1 use. | Temporary safety constraint | Current check-then-open code is vulnerable to TOCTOU races. |

## Security claims we cannot make yet

- E1 is **not** a race-free filesystem sandbox.
- Windows junction/reparse-point rejection is **not yet demonstrated**.
- Neither OS-specific sandboxing nor command execution isolation is implemented.
- Passing unit tests does not imply full security coverage.
