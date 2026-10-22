# ADR-006 — Windows DACL inspection is not isolation attestation

Status: partial implementation; runtime verification pending.

## Problem
Windows workspace mutation requires separation between trusted Enforcer authority and untrusted process authority. A directory being private or having a DACL does not establish this separation.

## Hypothesis
A native preflight can reject obviously unsafe workspace roots (reparse points and null DACLs), but must not grant mutation authority without effective-access verification using a restricted child token and a real denied-write experiment.

## Change
`enforcer-isolation::windows::inspect_windows_dacl` uses `GetNamedSecurityInfoW` to require a non-null DACL and rejects reparse-point roots. The returned `DaclState::Present` is intentionally **not** a verified isolation capability. Security descriptor memory is released with `LocalFree`.

## Security limitations
- A non-null DACL can still grant write access to untrusted identities, including via inherited ACEs.
- The API performs a name-based metadata inspection; it is not an atomic guarantee against concurrent directory replacement.
- No restricted token, separate identity, integrity-level restriction, inherited-handle audit, or Windows child negative-write test has been implemented in this patch.
- A privileged attacker or same-user process may retain alternate access. The isolation status remains `Unverified`.
- E2 versioned modification remains denied.

## Required next experiment
Provision a disposable protected workspace; launch an untrusted Windows child with an explicitly restricted token and no inheritable write handles; demonstrate that trusted writes succeed and child writes fail. Validate effective DACL access against the actual child token. Fail closed on any setup failure. Then separately test reparse-point and concurrent replacement attacks.

## Verification
Archive generation does not establish compilation. Run Windows and Ubuntu workspace checks; Windows native FFI and tests require Windows CI. No runtime security result is claimed here.
