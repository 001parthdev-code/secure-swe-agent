# E1 Iteration 5 — Adversarial filesystem validation

Date: 2026-10-21. Status: **candidate tests; execution pending**.

## Objective and trust assumptions
An untrusted agent controls requested paths and may change entries inside the workspace concurrently. The enforcer retains a trusted workspace directory handle. The operating system and enforcer process are trusted; a privileged attacker controlling the kernel or process is out of scope.

## Hypotheses
- H1: A nested Windows junction cannot redirect a successful read outside the workspace.
- H2: A Linux attacker repeatedly swapping a real directory with an external symlink cannot cause an outside read.
- H3: A held workspace handle does not silently switch to a replacement pathname after a successful root rename.
- H4: Nested regular files remain readable, while directory reads and traversal are rejected.

## Changes
- Add `security_adversarial.rs` with nested-file, directory-object, nested-junction, Linux concurrent-symlink-swap, and root-handle tests.
- Register the test module in `main.rs`.
- Preserve the existing E1 filesystem implementation. **No security implementation changes are claimed in this patch.**

## Verification and interpretation
Run `cargo fmt`, `cargo test`, and `cargo clippy --all-targets -- -D warnings` on Windows and Linux. The Windows junction fixture fails the test if creation fails. The root-rename test is conditional on rename being supported; a pass without rename must not be counted as proof of root-replacement resistance. The Linux stress test is nondeterministic and can reveal an escape, but a pass is not a proof of race freedom. Repeat stress tests under load.

## Open review items
- Audit Windows `NtCreateFile` behavior for **intermediate** reparse points and object-manager paths; the final-handle attribute check alone does not establish that intermediate traversal is safe.
- Audit Windows UTF-16 conversion and path-component normalization; lossless conversion is preferable to `to_string_lossy()` for security-sensitive path handling.
- Audit Linux `openat2` flags, kernel support, and non-regular objects.
- Ensure documentation reflects actual test evidence rather than assuming all race scenarios were covered.

## Observations
Earlier Iteration 4 was initially delivered without claimed modules; corrected modules were subsequently integrated. User reported Windows local tests and Windows/Ubuntu CI passing. **This Iteration 5 patch has not been compiled or tested here.** Record actual results after execution.
