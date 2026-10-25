# E2 Windows token-startup differential diagnostic

## Observed failure
The restricted Windows startup-only probe exits with `0xC0000022` before creating a marker. The normal-user write probe can run. This is a process-initialization failure, **not** evidence of workspace write denial.

## Hypothesis
A token using the BUILTIN\\Users restricting SID may be unable to access a Windows startup dependency even though the probe executable and selected DLLs have RX permissions.

## Change
The diagnostic launcher offers `--diagnose-privileges-only`, which creates a token with privileges removed but **no restricting SID**, and runs only the startup probe. The strict `--startup-only` and protected write test retain their existing restricting SID and must still pass for isolation acceptance.

## Interpret results
- Diagnostic fails: investigate token type, launch API, process startup, and system resource access before blaming the restricting SID.
- Diagnostic passes, strict startup fails: investigate restricting-SID access checks and required OS resources. Do not treat the diagnostic as security success.
- Both startup controls pass: run the protected negative-write test and verify its marker and result.

## Limitations
No OS-enforced isolation is certified by this diagnostic. It must never be used as a fallback for production or the protected write experiment. The patch has not been compiled or executed on Windows in this environment.
