# E2 Linux atomic replacement — experimental implementation

## Objective
Implement a complete bounded staged-write/rename primitive against a pinned workspace directory descriptor, without exposing it to untrusted agent requests.

## Assumptions and limitations
- Linux 5.6+ `openat2` support, same-filesystem staging and destination.
- The caller already authorized the operation and guarantees exclusive mutation authority over the target and parent directory throughout the operation. `flock` coordinates only cooperating writers and **does not** enforce this against adversarial processes.
- This code is **not** a security-verified compare-and-swap primitive: an external writer could replace the directory entry after revalidation and before rename. No public protocol integration is enabled.
- Successful rename is atomic for directory-entry replacement, but it replaces the inode. Existing file descriptors still reference the old inode. Metadata/ownership/permissions are not preserved: new staging files use mode 0600.
- `sync_all` of staged content and parent directory is attempted. A directory sync failure after rename has ambiguous commit outcome; never retry blindly.
- A process crash before rename can leave a hidden staging file. Recovery and scavenging are not yet implemented.
- Version snapshots compare inode/device and bytes; they are not portable durable version identifiers.

## Implementation
- `enforcer-transaction/src/atomic_linux.rs`: directory-relative O_EXCL staging, fsync, revalidation, renameat, parent fsync, cleanup on precommit failure.
- Existing `version.rs`: descriptor snapshot and revalidation.
- No changes to CLI or authorization policy. Windows unaffected.

## Tests
- Successful replacement and stale-version rejection.
- Oversized content rejection with unchanged destination.
- Existing Linux workspace tests remain mandatory.

## Verification status
Source patch prepared. Rust compilation and Linux CI have not been executed in the authoring environment. Do not enable `modify_file_versioned` until exclusive authority, path-entry concurrency, crash recovery and metadata semantics are addressed and verified.

## Next
Run CI, correct any compiler or runtime failures, then implement a true exclusive mutation boundary and recovery strategy before public enablement.
