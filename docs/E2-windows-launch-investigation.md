# E2 Windows restricted-token launcher investigation

## Observation
Local experiment returned Win32 1314. `CreateProcessWithTokenW` requires SeImpersonatePrivilege; the reported ordinary-user token lacks that privilege. GitHub Actions previously reported Win32 87. Neither failure proves an isolation bypass.

## Hypothesis
A restricted primary token can be launched with `CreateProcessAsUserW` when the calling process has the required privileges; `CreateProcessWithTokenW` is an alternative only when SeImpersonatePrivilege is available.

## Change
Attempt `CreateProcessAsUserW` first with `bInheritHandles=FALSE`; only if it returns 1314 attempt `CreateProcessWithTokenW` with the same restricted token, without profile loading. Report the failing API and OS error. Never launch with the unrestricted token. Local PowerShell harness uses a local temp path when RUNNER_TEMP is unset.

## Security limits and acceptance
This is a diagnostic, fail-closed launcher correction, not an ordinary-user isolation solution or production attestation. Both APIs may fail on ordinary-user tokens. Successful process launch alone does not prove the child actually has the intended restricted token, nor that all access paths are denied. A future implementation must inspect the child's effective token, prove denied direct writes, prevent inherited writable handles, and verify the workspace ACL. The test must fail if a restricted process cannot be launched.

## Verification
Not executed in this environment. Run `cargo fmt --all`, `cargo test --workspace --locked`, and `cargo clippy --workspace --all-targets --locked -- -D warnings`, then the Windows runtime experiment. Record actual results; do not mark Windows isolation verified without a passing runtime test.
