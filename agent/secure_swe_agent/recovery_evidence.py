"""Read-only evidence collection for interrupted A7 operations.

Evidence is descriptive, never authorization to replay an operation or mark it
successful. Operator must verify provenance and resolve uncertain outcomes.
"""
from __future__ import annotations

import hashlib
import subprocess
from pathlib import Path

from .workflow_state import WorkflowStore, StateError


def filesystem_evidence(store: WorkflowStore, workflow_id: str,
                        relative: str, expected_sha256: str) -> dict:
    row = store.get(workflow_id)
    if row["state"] != "needs_reconciliation":
        raise StateError("workflow is not awaiting reconciliation")
    if not isinstance(expected_sha256, str) or len(expected_sha256) != 64 or any(
        c not in "0123456789abcdef" for c in expected_sha256
    ):
        raise StateError("invalid expected digest")
    rel = Path(relative)
    if rel.is_absolute() or not rel.parts or any(part in (".", "..") for part in rel.parts):
        raise StateError("invalid evidence path")
    root = Path(row["repo"]).resolve(strict=True)
    # No symlinks anywhere in the inspected path; this is not a hostile-writer
    # resistant operation and is only valid for operator-controlled fixtures.
    candidate = root
    for part in rel.parts:
        candidate = candidate / part
        if candidate.is_symlink():
            raise StateError("evidence path contains symlink")
    if not candidate.is_file():
        return {"kind": "filesystem", "outcome": "missing", "matches": False}
    actual = hashlib.sha256(candidate.read_bytes()).hexdigest()
    return {"kind": "filesystem", "outcome": "observed", "matches": actual == expected_sha256,
            "actual_sha256": actual}


def git_evidence(store: WorkflowStore, workflow_id: str, expected_commit: str) -> dict:
    row = store.get(workflow_id)
    if row["state"] != "needs_reconciliation":
        raise StateError("workflow is not awaiting reconciliation")
    if not (len(expected_commit) in (40, 64) and all(c in "0123456789abcdef" for c in expected_commit)):
        raise StateError("invalid expected commit")
    repo = Path(row["repo"]).resolve(strict=True)
    result = subprocess.run(["git", "-C", str(repo), "rev-parse", "HEAD"],
                            capture_output=True, text=True, timeout=10, check=False,
                            env={"GIT_CONFIG_NOSYSTEM": "1"})
    if result.returncode:
        return {"kind": "git", "outcome": "unavailable", "matches": False}
    observed = result.stdout.strip()
    return {"kind": "git", "outcome": "observed", "matches": observed == expected_commit,
            "actual_commit": observed}


def github_evidence(store: WorkflowStore, workflow_id: str, *, github_repo: str,
                    branch: str, expected_commit: str, base: str,
                    title: str, body: str, token: str) -> dict:
    """Read-only remote evidence; never resolves or replays a publication.

    Uses the existing GitHub broker's validated origin, remote-head and PR
    inspection. A missing PR is not proof that creation did not occur.
    """
    import re
    from .github_broker import _origin, _remote_head, _existing_pr
    row = store.get(workflow_id)
    if row["state"] != "needs_reconciliation":
        raise StateError("workflow is not awaiting reconciliation")
    if not re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", expected_commit):
        raise StateError("invalid expected commit")
    if not re.fullmatch(r"agent/task-[A-Za-z0-9_.-]+", branch):
        raise StateError("invalid task branch")
    if base not in ("main", "master") or not token:
        raise StateError("invalid remote evidence parameters")
    repo = Path(row["repo"]).resolve(strict=True)
    _origin(repo, github_repo)
    observed = _remote_head(repo, branch)
    if observed is None:
        return {"kind": "github", "outcome": "branch_missing", "matches": False,
                "pr": "not_checked"}
    if observed != expected_commit:
        return {"kind": "github", "outcome": "branch_conflict", "matches": False,
                "observed_commit": observed, "pr": "not_checked"}
    pr = _existing_pr(github_repo, branch, base, expected_commit, title, body, token)
    return {"kind": "github", "outcome": "matching_pr" if pr else "pr_not_observed",
            "matches": bool(pr), "observed_commit": observed,
            "pr": pr["url"] if pr else None}
