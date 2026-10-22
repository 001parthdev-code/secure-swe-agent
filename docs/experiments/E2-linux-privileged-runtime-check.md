# E2 Linux privileged negative-write integration check

## Objective and hypothesis
A disposable workspace owned by the trusted identity, with mode `0700` and non-writable ancestors, permits trusted writes while rejecting a direct file creation attempt from a separately identified untrusted process.

## Assumptions
- Runs only on a disposable Ubuntu CI host where the runner has passwordless `sudo` and a non-root `nobody` account.
- `/opt` and its ancestors are root-owned and not group/world-writable. The Rust prerequisite checker enforces the latter condition.
- The probe binary is trusted and staged in a temporary executable directory.
- This experiment does **not** certify the Enforcer's production sandbox, ACLs, capabilities, supplementary groups, mount namespaces, inherited descriptors, or alternative write paths.

## Changes
- `enforcer-isolation-runtime-check` creates a fresh root-owned `/opt/enforcer-isolation-ci-*` workspace with `0700` permissions, performs a trusted write control, invokes `probe_untrusted_create`, checks the explicit denial marker and absence of an unauthorized entry, and cleans up the workspace.
- `scripts/verify-linux-isolation.sh` builds the two binaries, stages the probe, and runs the integration check under `sudo` using the `nobody` UID/GID.
- The Ubuntu CI workflow adds a **separate required-to-inspect job**, which fails if the probe cannot run or does not observe denial. It does not silently skip on missing privilege.

## Evidence status
- Rust compilation: **pending**.
- Ubuntu privileged experiment: **pending** until the new GitHub Actions job completes.
- Windows equivalent: **not implemented**.

## Acceptance criteria
1. Trusted write control succeeds.
2. Untrusted probe confirms its effective UID and receives `PermissionDenied` on create.
3. No unauthorized file exists after the attempt.
4. Any missing precondition or probe failure causes nonzero CI exit.

## Limitations and next work
This is one negative-write experiment, not proof of exclusive mutation authority. The isolation API remains `Unverified` and `modify_file_versioned` remains denied. Next: supplementary-group and inherited-descriptor hygiene, multi-path negative tests, and Windows restricted-token/DACL implementation.
