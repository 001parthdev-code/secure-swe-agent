# E1 Iteration 4 correction — engineering record

**Status:** implementation delivered; verification pending.

**Observation:** previous E1 Iteration 4 patch was reported as handle-relative but repository contained only main.rs, policy.rs, protocol.rs. CI results did not establish that the claimed implementation was present.

**Assumption:** trusted workspace root at process startup; attacker may mutate entries below it. Supported targets: Windows 10/11 and Linux >=5.6 on x86_64/aarch64.

**Hypothesis:** OS-enforced handle-relative no-reparse resolution prevents workspace escapes under concurrent path swaps.

**Change:** introduce secure_fs module with Linux openat2 and Windows NtCreateFile; connect policy read_file to the new layer; preserve strict Windows junction regression test.

**Expected outcome:** normal workspace reads succeed; symlinks/junctions and traversal fail; no fallback to check-then-open pathname logic.

**Actual outcome:** pending Windows and Ubuntu builds and adversarial tests. No security guarantee claimed yet.

**Risks:** Windows NT API behavior, NT object namespace edge cases, Linux mount behavior, platform architecture support, and concurrent rename stress require review.
