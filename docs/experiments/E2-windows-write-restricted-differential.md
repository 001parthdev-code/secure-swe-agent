# E2 Windows WRITE_RESTRICTED differential experiment

## Hypothesis
The strict token fails during loader initialization because restricting SIDs are applied to read/execute access checks. Windows `CreateRestrictedToken` flag `WRITE_RESTRICTED` (0x8) applies the restricting SID list to write checks rather than general read/execute checks. This is a **hypothesis**, not a verified root cause.

## Changes
- Add `--diagnose-write-restricted-startup` and `--diagnose-write-restricted-write` to the Windows runtime checker.
- Both use `DISABLE_MAX_PRIVILEGE | WRITE_RESTRICTED` and retain the `BUILTIN\\Users` restricting SID.
- The PowerShell harness runs the startup control and, only if it succeeds, the protected write-denial control.
- Existing strict `--startup-only` and default strict write probe are unchanged and still required to pass for CI acceptance.

## Expected evidence
1. Privilege-only startup control result.
2. Everyone-SID control result.
3. WRITE_RESTRICTED startup marker and exit code.
4. WRITE_RESTRICTED protected write probe marker, exit code, and absence of unauthorized file.
5. Strict-token startup and strict protected write test results.

## Limits
WRITE_RESTRICTED is not a confidentiality boundary. It can allow reads that the original strict restricting-SID token would deny. The diagnostic is **not** a production isolation attestation, even if both controls pass. A successful negative-write experiment is only one property; token identity, inherited handles, alternate paths, race conditions, and deployment policy remain to be verified. Do not relax workspace DACLs or use the diagnostic token as a silent fallback.

## Status
Unexecuted candidate. Windows compilation and runtime experiment required.
