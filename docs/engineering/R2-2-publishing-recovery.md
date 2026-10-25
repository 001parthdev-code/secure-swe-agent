# R2.2 — GitHub publication recovery

Scope: trusted operator-controlled Git broker, disposable/trusted repositories only.

## Changes
- Validate approved plan before network operations.
- Read remote task branch before pushing; refuse to overwrite a different remote commit.
- Look up open PRs for the exact source branch and base. Return a matching existing PR, reject a conflicting PR.
- If the approved branch already exists at the approved commit, skip pushing and proceed to PR creation.
- Verify remote branch after pushing, before creating a PR.
- On HTTP 422, recheck whether an identical PR already exists.
- Fail closed on uncertain API or remote state, with explicit partial-publication errors.

## Known limitations
- Remote URL rewriting and operator-controlled Git configuration remain trusted; this is not a hostile-repository Git sandbox.
- GitHub API and Git transport are separate authentication channels.
- A crash between the push and API call is recoverable by retrying with the same approval and unchanged commit.
- A crash after PR creation is recoverable by finding the existing matching PR.
- Concurrent publication actors and malicious mutation of local Git configuration are not fully addressed.
- Existing PR lookup considers open PRs; closed PRs are not treated as successful publication.

## Verification
`python -m unittest discover -s agent/tests -v`

New offline tests cover matching existing PR, remote mismatch, already-pushed branch, conflicting PR, and post-push remote verification. Live GitHub integration remains a separate acceptance check.
