# Windows WRITE_RESTRICTED negative-write CI milestone (candidate)

## Source baseline
Based on the uploaded `secure-swe-agent (2).zip`. Only the files listed in this patch are changed.

## Decision
The existing strict `BUILTIN\Users` restricting-SID startup failure remains unresolved. For the **write-isolation creation experiment only**, make `DISABLE_MAX_PRIVILEGE | WRITE_RESTRICTED` the explicit mandatory acceptance mode. The legacy strict startup test is an opt-in diagnostic (`ENFORCER_RUN_LEGACY_STRICT_DIAGNOSTIC=1`) and cannot certify this different mode.

## Required runtime evidence
- Trusted user writes a control file in the disposable protected directory.
- Restricted child executes startup control and writes a marker outside the protected directory.
- Child's write probe checks `IsTokenRestricted`, writes an attempt marker, and tries `OpenOptions::create_new` inside the protected directory.
- Probe returns zero **only** on `PermissionDenied`; checker verifies marker content and absence of the target.
- Child timeout is bounded to 30 seconds; timeout is failure, not success.

## Scope and limitations
This experiment does **not** certify production process isolation. Existing-file modification, deletion, rename, ACL manipulation, alternate paths, inherited handles, child process spawning, read confidentiality, and transaction integration remain unverified. The public versioned modification operation must remain disabled. The PowerShell harness is a disposable test fixture and must not be reused as a production provisioning API.

## Verification pending
Rust compilation, Windows execution, Ubuntu checks, and CI have **not** been executed in the authoring environment. Apply patch and run `cargo fmt --all -- --check`, `cargo test --workspace --locked`, `cargo clippy --workspace --all-targets --locked -- -D warnings`, then `scripts/verify-windows-isolation.ps1`. Confirm Windows/Ubuntu/Linux-negative-write/Windows-negative-write CI jobs all pass.
