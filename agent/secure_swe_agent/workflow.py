"""A7 supervised workflow: no implicit mutation, commit, or remote publishing."""
from __future__ import annotations

import json
import re
from pathlib import Path

from .approval import apply_approved, digest, load_proposal
from .enforcer import EnforcerClient
from .git_broker import GitBrokerError, _branch, _git, _root, create_task_branch, prepare_commit, commit_approved
from .github_broker import preview_publish, publish_approved
from .verification import verify_calculator_fixture


class WorkflowError(ValueError):
    pass


def _proposal(proposal_file: Path) -> tuple[dict, str]:
    raw = Path(proposal_file).read_bytes()
    return load_proposal(raw), digest(raw)


def _file(proposal: dict) -> str:
    return proposal["changes"][0]["path"]


def _fixture(repo: Path, workspace: Path, relative: str) -> None:
    repo = _root(repo)
    workspace = Path(workspace).resolve(strict=True)
    if workspace != (repo / "workspace").resolve() or relative != "calculator/calculator.py":
        raise WorkflowError("A7 demo supports only the trusted calculator fixture under repo/workspace")
    if (workspace / "calculator").is_symlink():
        raise WorkflowError("linked fixture denied")


def prepare(repo: Path, proposal_file: Path, slug: str) -> dict:
    proposal, fingerprint = _proposal(proposal_file)
    relative = _file(proposal)
    _fixture(repo, Path(repo) / "workspace", relative)
    repo = _root(repo)
    branch = create_task_branch(repo, slug)
    return {"status": "awaiting_apply_approval", "branch": branch,
            "path": relative, "proposal_sha256": fingerprint,
            "diff_untrusted": proposal["changes"][0].get("diff", ""),
            "warning": "Review proposed content; no file has been modified."}


def apply(repo: Path, proposal_file: Path, approved_sha256: str, enforcer_binary: Path) -> dict:
    proposal, fingerprint = _proposal(proposal_file)
    if not re.fullmatch(r"[0-9a-f]{64}", approved_sha256) or approved_sha256 != fingerprint:
        raise WorkflowError("proposal changed since approval")
    repo = _root(repo)
    _branch(repo)
    relative = _file(proposal)
    workspace = repo / "workspace"
    _fixture(repo, workspace, relative)
    if _git(repo, "status", "--porcelain", "--untracked-files=all"):
        raise WorkflowError("working tree must be clean before application")
    with EnforcerClient(enforcer_binary, workspace, trusted_exclusive=True) as client:
        result = apply_approved(proposal, client, {relative})
    if result.get("status") != "applied":
        return result
    verification = verify_calculator_fixture(workspace)
    return {"status": "verified" if verification["verified"] else "verification_failed",
            "verification": verification, "path": relative,
            "next": "Review Git staged diff; no automatic commit or push."}


def review_commit(repo: Path, relative: str) -> dict:
    if relative != "workspace/calculator/calculator.py":
        raise WorkflowError("A7 demo only permits the calculator source file")
    return prepare_commit(repo, relative)


def commit(repo: Path, relative: str, approved_sha256: str, message: str) -> dict:
    if relative != "workspace/calculator/calculator.py":
        raise WorkflowError("A7 demo only permits the calculator source file")
    # Re-run trusted fixture verification immediately before committing.
    result = verify_calculator_fixture(_root(repo) / "workspace")
    if not result["verified"]:
        raise WorkflowError("verification failed; commit denied")
    return commit_approved(repo, relative, approved_sha256, message)


def review_publish(repo: Path, github_repo: str, base: str, title: str, body: str) -> dict:
    return preview_publish(repo, github_repo, base, title=title, body=body)


def publish(repo: Path, github_repo: str, base: str, title: str, body: str, approval: str) -> dict:
    return publish_approved(repo, github_repo, approval, base=base, title=title, body=body)
