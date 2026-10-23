# E2 Windows restricted-token launch context — experiment

## Observation
Privilege-stripped startup succeeded; strict restricting-SID startup failed before its marker. A diagnostic Everyone-SID variant returned `STATUS_DLL_NOT_FOUND` (`0xC0000135`). Neither outcome proves that the protected write was attempted.

## Hypothesis
Inheriting an arbitrary working directory or reusing a Win32-modified command-line buffer could contribute to restricted process initialization failures. This is a testable hypothesis, not an established root cause.

## Changes
- Set the child working directory explicitly to the provisioned diagnostic directory for both process-launch APIs.
- Reconstruct the mutable command-line buffer before fallback to `CreateProcessWithTokenW`.
- Preserve the strict Users-SID startup and negative-write checks as mandatory gates. A failed Everyone-SID differential diagnostic is recorded but does not prevent the strict test from running.
- On failure, print ACLs for the diagnostic directory, probe, and protected workspace. Do not modify them.

## Verification required
1. `cargo fmt --all -- --check`, `cargo test --workspace --locked`, `cargo clippy --workspace --all-targets --locked -- -D warnings`.
2. Run `scripts/verify-windows-isolation.ps1` on Windows; record the precise startup outcome.
3. The restricted startup marker **and** the protected negative-write test must both succeed before accepting Windows isolation.
4. Confirm all CI jobs. No production isolation attestation is issued by this patch.

## Limitations
The patch does not establish the cause of the loader error, verify all token groups, or implement production sandbox isolation. `modify_file_versioned` remains disabled.
