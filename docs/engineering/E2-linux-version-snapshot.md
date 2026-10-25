# E2 Linux version snapshot — implementation increment

## Scope
Adds a bounded descriptor-based snapshot and revalidation building block to `enforcer-transaction`. Does not modify files or enable `modify_file_versioned`.

## Security assumptions
- The supplied descriptor refers to a regular file opened securely by the caller.
- The caller must establish exclusive OS-enforced workspace mutation authority before using revalidation to authorize a commit.
- Comparing the opened object is not sufficient to prove that its directory entry still names the same object.

## Invariants and limitations
- Snapshot rejects files larger than 1 MiB.
- Snapshot records Linux device/inode identity and exact file bytes; no hash collision assumptions.
- Revalidation detects changed bytes or opened-object identity, but does not close concurrent modification races without external exclusion.
- Snapshot is not a serialized version token, durable identity, or atomic commit.
- Concurrent in-place changes during reading may not be detected in all cases; OS-level exclusion is mandatory before production use.

## Tests
- Same-length content modification invalidates snapshot.
- Oversized file rejected.

## Next
Implement Linux exclusive workspace ownership and pinned-parent target-entry revalidation, then staged rename commit and fault-injection tests. Keep public versioned modification denied until end-to-end proof.
