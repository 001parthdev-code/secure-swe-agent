# E2 — Threat model and transaction specification (ADR candidate)

Status: **Design approved; implementation and security acceptance NOT complete.**

## Scope and trust boundary
The untrusted agent controls request fields and repository contents. The Rust Enforcer authorizes operations. The OS and kernel are trusted, but arbitrary other processes with write privileges to the workspace are not. Local administrators/root and kernel compromise are out of scope. Network shares and filesystems without required atomic rename/durability semantics are unsupported until validated.

## Approved security properties
- SEC-01: Default deny, explicit separate create and modify capabilities.
- SEC-02: No traversal outside pinned workspace handles; symlink/reparse escape rejected.
- SEC-03: Modify a *logical target version* only if it matches the version authorized by the Enforcer; reject conflicts.
- SEC-04: Publish complete new bytes atomically; no partial visible content.
- SEC-05: Pre-commit failures preserve previously committed content.
- SEC-06: External concurrent mutation cannot defeat SEC-03; a process-local mutex is insufficient.
- SEC-07: Private staging and cleanup; durability guarantees separately specified.
- SEC-08: Record authorization, conflict, commit, abort and error outcomes.

## Architecture and OS-enforced concurrency
The supported workspace must be **exclusively writable by the trusted Enforcer identity**, with the agent and its tools running under a distinct, restricted OS identity. A second privileged or same-identity process is not assumed trustworthy. Windows: validate ACLs, handle inheritance and share modes, and prevent untrusted processes from obtaining workspace write handles. Linux: validate mount/user namespace policy and writable bind mounts; use dedicated UID and controlled directory permissions. These controls must be provisioned and verified by a launcher; *not* merely documented or inferred from pathname ownership. Fail closed if isolation is unavailable. OS privileged processes remain outside this guarantee.

## Logical identity and version tokens
A logical target is `(workspace_id, parent_directory_identity, normalized_component_name, version)`. Version tokens are opaque, issued by the Enforcer after reading an authorized snapshot, and bind target identity plus content digest or generation. An agent-supplied arbitrary version string is **never trusted**. Revalidation must occur under enforced exclusive mutation authority. Hardlinks, case folding, Unicode names, rename behavior and external metadata changes require explicit platform tests.

## Proposed transaction state machine
`Authorize -> ResolvePinnedParent -> AcquireMutationAuthority -> VerifyVersion -> StagePrivate -> SyncStaged -> Revalidate -> AtomicCommit -> SyncDirectory -> AuditSuccess`; errors before commit -> `Abort -> Cleanup -> AuditFailure`. Commit-point failures need an explicit indeterminate-outcome response if durability cannot be determined; do not claim rollback after a successful rename.

`create_file`: retain no-overwrite atomic semantics. `modify_file` and `modify_file_versioned`: **deny** until version issuance, OS-enforced exclusive mutation, commit and recovery are implemented and tested. Atomic rename alone is not a conditional compare-and-swap.

## Platform notes
Linux: pinned dirfd, `openat2` constrained traversal, staged file on same filesystem, `renameat2` commit; `renameat2` has no destination-inode compare-and-swap. Windows: pinned directory handles, reparse-point-safe component traversal, staged replacement using appropriate NT rename facilities; rename-by-name alone is not conditional on target identity. Both require isolation that excludes hostile external writers, or an alternative transactional filesystem backend with equivalent guarantees.

## Attack/verification matrix (pending)
1. Malicious relative/absolute paths, symlinks, junctions, reparse points and hardlinks.
2. Concurrent parent swap, destination swap, rename, delete, and recreation.
3. Concurrent legitimate transactions with stale version tokens (exactly one commit).
4. Pre-commit crash, disk-full, access-denied, and interrupted staging: original bytes remain.
5. Post-commit crash: explicitly documented durability/recovery result.
6. Workspace ACL/mount isolation failure: modification denied.
7. Staging files inaccessible to untrusted identity; failed staging cleaned.
8. Windows and Linux CI plus separate adversarial integration tests with actual isolated principals.

## Evidence and current outcome
The earlier 17 Windows tests and green CI were reported for a fail-closed E2 patch. They do **not** validate a functional transactional modify implementation. This patch adds a versioned request shape and keeps it denied. Compilation/tests of this patch remain pending. No claim of completed E2 is made.
