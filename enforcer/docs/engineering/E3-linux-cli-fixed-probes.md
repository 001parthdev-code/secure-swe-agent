# E3 fixed-probe CLI integration — controlled prototype

## Scope
Connect the existing Linux-only `enforcer-execution` library to `run_command` in `enforcer-core` without accepting arbitrary executables, arguments, or shells. `true` and `false` are the only accepted names.

## Operator-controlled preconditions
The trusted operator sets `ENFORCER_ENABLE_FIXED_EXECUTION=1`, `ENFORCER_EXEC_UID`, and `ENFORCER_EXEC_GID`. Both IDs must be nonzero. The execution library also requires an effective-root supervisor and drops groups and child UID/GID before `exec`. Requests cannot set the identity. Unconfigured execution is denied. Windows denies all execution.

## Verification
The Linux CI integration checks default denial, unknown-command denial, and the fixed true/false probes under a disposable root-owned supervisor with a separate `nobody` identity. These tests do not attest filesystem, network, mount, process-tree, or syscall isolation.

## Known gaps
No arbitrary commands, arguments, output capture, sandbox root, Landlock, seccomp, cgroups, or process-tree kill. Child has a 3-second timeout but descendants are not tracked. Root supervisor is suitable only for this disposable CI experiment, not production deployment. Do not expose this endpoint to hostile workloads as a general command sandbox.

## Engineering decision
Preserve fail-closed public behavior unless the operator explicitly enables this narrowly scoped test. E3 production readiness requires a dedicated supervisor, comprehensive OS isolation, and adversarial verification.
