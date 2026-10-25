# E2 Linux versioned modification — end-to-end integration test

## Scope
This test runs a single long-lived `enforcer-cli` process against a disposable temporary workspace. It explicitly sets `ENFORCER_TRUSTED_EXCLUSIVE_WORKSPACE=1` for the test process only. The test is **not** evidence of exclusive mutation authority or OS-enforced isolation. Never use the flag as a substitute for such authority in production.

## Assertions
1. `get_file_version` returns a process-local token.
2. Invalid token is rejected without changing the target.
3. Valid token permits a replacement, and disk content changes.
4. Replaying the consumed token fails and preserves the replacement.
5. External modification after observation produces a stale-version rejection and preserves external content.
6. Missing target and traversal are rejected.

## Limitations
This test does not prove resistance to concurrent hostile writers, symlink swaps during commit, crash durability, metadata preservation, sandbox escape, or production deployment safety. Those remain open release gates.

## Execution
`cargo build --locked -p enforcer-cli && python3 scripts/verify-linux-e2-versioned.py target/debug/enforcer-cli`
