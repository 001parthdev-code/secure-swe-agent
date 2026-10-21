# E2 identity-preserving modification: fail-closed correction (2026-10-21)

## Approved invariant
`modify_file` must only replace the exact file object originally authorized, and reject concurrent substitution.

## Finding / hypothesis
The existing Linux `renameat2` and Windows `NtSetInformationFile` name-based replacement commit cannot atomically assert the identity of the destination previously opened. A last-moment metadata comparison is not sufficient: a concurrent rename can occur after the comparison.

## Change
Both policy and platform filesystem write functions now reject `modify_file` before staging, opening a writable destination, or committing. `create_file` and E1 reads remain available. The Windows staged-file cleanup from the prior remediation patch is retained. Tests previously asserting successful modification are revised to assert denial and unchanged content.

## Tradeoff
This is a **security-preserving feature restriction**, NOT an implementation of successful identity-preserving modification. E2 is NOT complete under the approved scope. A future design must specify a verifiable atomic identity-conditional commit or relax the requirement explicitly. Do not connect an untrusted agent to modify operations.

## Verification
Not executed in this environment. Run `cargo fmt`, `cargo fmt --check`, `cargo test --locked`, `cargo clippy --locked --all-targets -- -D warnings` on Windows, then Windows and Ubuntu CI. Test count is not an acceptance criterion.

## Residual risks
No claim is made that `create_file` is fully security-audited; concurrency and failure cleanup still require targeted verification.
