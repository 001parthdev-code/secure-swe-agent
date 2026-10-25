# E3.1 — Linux controlled execution prototype

## Scope
Introduces `enforcer-execution::run_fixed_probe` for fixed `/usr/bin/true` and `/usr/bin/false` probes. This is a **library-only** increment: the untrusted `run_command` JSON endpoint remains disabled. The launcher requires a root supervisor and explicit nonzero UID/GID, clears supplementary groups, sets `no_new_privs`, clears the environment, disables inherited standard streams, and enforces a 3-second timeout.

## Limitations and release gates
This is **not a sandbox**. It has no mount/network namespaces, Landlock, seccomp, cgroups, or process-tree cleanup. A timeout kills only the immediate child. A privileged supervisor must not accept arbitrary executable paths or UID/GID choices from an agent. Do not expose this library to untrusted requests until a separate isolation adapter and process-tree lifecycle are verified.

## Next step
Wire a trusted execution supervisor to a real Linux sandbox backend and add an end-to-end CI test. Keep `RunCommand` denied in `enforcer-core` until then.
