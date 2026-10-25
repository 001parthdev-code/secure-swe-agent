# A6 — Supervised GitHub publishing

This increment adds an **operator-only** GitHub publishing broker. It is not exposed as an LLM tool. A5 commits must already exist on `agent/task-*` branches.

## Approval contract

`preview` binds the GitHub repository, task branch, HEAD commit, base branch, PR title and body to a SHA-256 approval fingerprint. `publish` recomputes this fingerprint and rejects changes. It requires a clean working tree, a credential-free HTTPS `github.com` origin matching an explicitly provided `owner/repo`, and a `GH_TOKEN` environment variable for the GitHub REST API. Git push uses separately configured operator Git credentials. Only the approved task branch is pushed; no force push, no merge, no direct main/master push.

## Usage (trusted disposable repository only)

```powershell
python agent/github_approved.py --repo .\git-demo --github-repo OWNER/REPO --base main preview --title "Fix calculator subtraction" --body "Verified regression tests"
# Review branch, commit, target and fingerprint. Do not automate approval.
$env:GH_TOKEN = "..."  # Set securely; do not paste tokens into chat or commit them.
python agent/github_approved.py --repo .\git-demo --github-repo OWNER/REPO --base main publish --approve-sha256 ACTUAL_FINGERPRINT --title "Fix calculator subtraction" --body "Verified regression tests"
```

A6's unit tests are offline and do **not** push or create a real PR. An actual PR requires a GitHub repository, correct permissions and separate explicit operator approval. A successful push followed by a failed PR request leaves the branch on GitHub; inspect it before retrying.

## Known limitations

This is a functional supervised workflow, **not a secure broker for hostile repositories**. Git configuration and credential helpers are trusted; remote hooks and other external Git behavior are not fully controlled. The broker does not attest that a commit passed tests or that the branch is based on the latest default branch. PR creation is not a merge. Production hardening, sandboxed test execution and authorization provenance remain outstanding.
