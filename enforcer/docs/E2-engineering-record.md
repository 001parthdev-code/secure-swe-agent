# E2 — controlled writes: engineering record

## Decision
Separate `create_file` and `modify_file` actions. Legacy `write_file` remains denied. Existing E1 reads unchanged.

## Assumptions
- The workspace is trusted at initialization and its retained handle remains valid.
- The attacker controls request paths/content and may mutate workspace directory entries.
- Windows 10/11 and Linux 5.6+ only; no fallback to pathname-based resolution.
- E2 permits modifications to ordinary files within the workspace, including source files. External permission isolation remains a deployment responsibility.

## Hypotheses
- Handle-relative parent traversal rejects junction and symlink escapes.
- Linux temporary-file + `renameat2` prevents partially visible committed content under ordinary process interruption.
- Distinct create/modify dispositions prevent accidental overwrite and accidental creation.

## Implementation
- Linux: secure parent open via `openat2`, unique exclusive temporary file, `fsync`, `renameat2` (NOREPLACE on create), directory sync. Existing target checked with O_NOFOLLOW before modify.
- Windows: component-by-component NT handle traversal, FILE_CREATE / FILE_OVERWRITE, reject reparse final handle. **Windows modification is NOT atomic.** Failure may truncate an existing file.
- Both: maximum 1 MiB UTF-8 content, deny malformed paths, preserve legacy write denial.

## Important limitations and unresolved risks
- Windows FILE_OVERWRITE may truncate before final reparse verification. The final-object check is too late to guarantee no mutation of a hostile reparse target. Do not deploy E2 writes in adversarially mutable Windows workspaces until this is remediated.
- Linux modify checks target and then renames; a concurrent replacement may change which workspace entry is replaced, though containment remains relative to pinned parent handle.
- Linux atomic rename does not guarantee atomic multi-file transactions.
- Crash-durability guarantees depend on filesystem and storage behavior.
- No tests have been executed by the patch author. Cross-platform CI and adversarial validation are required.

## Verification plan
`cargo fmt --check`, `cargo test --locked`, `cargo clippy --locked --all-targets -- -D warnings` on both Windows and Ubuntu. Manually review Windows NT dispositions and concurrent reparse races before enabling write actions for untrusted agents.

## Status
**Candidate only; E2 is NOT accepted.**
