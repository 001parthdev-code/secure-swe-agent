# E2 Windows restricting-SID differential experiment

## Observation
The privilege-stripped startup probe succeeded, while the strict BUILTIN\Users restricting-SID startup exited with NTSTATUS 0xC0000022 before creating its marker.

## Hypothesis
The failure is related to an access check against the restricting SID set during process initialization.

## Change
Add a **diagnostic-only** startup control using the Everyone (`WinWorldSid`) restricting SID. It uses the same process launcher and marker-only startup probe. The original BUILTIN\Users restricting-SID startup and protected negative-write test remain mandatory and unchanged.

## Interpretation
- If Everyone-SID startup succeeds and Users-SID startup fails, investigate resources granting Everyone but not Users and the restricted token's effective access.
- If both fail, investigate resources required by any restricted token and the process initialization environment.
- Neither diagnostic establishes isolation. The strict child must run, reach the write operation, be denied, and leave no unauthorized file.

## Security limitations
No production attestation is issued. No protected workspace DACL or child write permissions are relaxed. This patch is not a fix for the strict restricted-token startup failure.

## Verification
Windows compilation, unit tests, Clippy, then run `scripts/verify-windows-isolation.ps1`. Record each diagnostic result and the strict test result.
