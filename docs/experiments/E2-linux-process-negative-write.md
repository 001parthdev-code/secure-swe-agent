# E2 — Linux restricted-process negative-write probe

## Problem
Metadata-only isolation checks cannot demonstrate that a distinct process identity is denied direct writes.

## Assumptions
- Linux and a trusted `enforcer-isolation-probe` executable.
- A workspace owned by the trusted Enforcer UID, with no group/world-writable ancestor (the current conservative prerequisite).
- A separately provisioned, non-root untrusted UID/GID; the caller must be authorized to launch under that identity.
- This probe checks only one direct file-creation attempt, not all filesystem access paths.

## Hypothesis
Launching a child under the untrusted credentials will produce an explicit permission-denied result when it attempts to create a fresh file inside the protected workspace.

## Changes
- Added a purpose-built probe binary that checks its effective UID and attempts exclusive creation.
- Added `probe_untrusted_create` which launches that binary with Linux UID/GID credentials and requires a precise denial marker, success exit status, and no residual file.
- Added negative-path unit tests.

## Verification
- Local Windows: not applicable to the Linux implementation.
- Linux compile and unit tests: **pending**.
- Privileged, separately provisioned UID/GID integration experiment: **pending**. Ordinary CI must not count an unexecuted privileged probe as passed.

## Security limitations
A negative result does **not** certify exclusive mutation authority. It does not verify supplementary groups, ACLs, inherited descriptors, process capabilities, alternate mount paths, or malicious privileged host processes. The public isolation status remains `Unverified`; versioned modification remains disabled.

## Next steps
Implement controlled credential provisioning and inherited-handle hygiene, add a privileged Linux integration job, and develop Windows token/DACL equivalents. Audit all alternative mutation paths before enabling `Verified`.
