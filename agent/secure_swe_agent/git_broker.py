"""A5 supervised local Git broker. No push, fetch, merge or network operations."""
from __future__ import annotations

import hashlib
import re
import subprocess
import tempfile
from pathlib import Path


class GitBrokerError(ValueError):
    pass


def _git(repo: Path, *args: str) -> str:
    # Disable repository hooks for this trusted-operator Git workflow.
    with tempfile.TemporaryDirectory(prefix="swe-empty-hooks-") as hooks:
        result = subprocess.run(
            ["git", "-c", f"core.hooksPath={hooks}", "-C", str(repo), *args],
            capture_output=True, text=True, timeout=20, check=False,
        )
    if result.returncode:
        raise GitBrokerError(f"git {args[0]} failed (exit {result.returncode})")
    return result.stdout


def _root(repo: Path) -> Path:
    repo = Path(repo).resolve(strict=True)
    top = Path(_git(repo, "rev-parse", "--show-toplevel").strip()).resolve()
    if top != repo:
        raise GitBrokerError("repository must be its top-level directory")
    if _git(repo, "rev-parse", "--is-bare-repository").strip() != "false":
        raise GitBrokerError("bare repository not supported")
    return repo


def _branch(repo: Path) -> str:
    branch = _git(repo, "symbolic-ref", "--quiet", "--short", "HEAD").strip()
    if not re.fullmatch(r"agent/task-[a-z0-9][a-z0-9-]{0,49}", branch):
        raise GitBrokerError("must be on an agent/task-* branch")
    return branch


def create_task_branch(repo: Path, slug: str) -> str:
    repo = _root(repo)
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,49}", slug):
        raise GitBrokerError("invalid task slug")
    if _git(repo, "status", "--porcelain", "--untracked-files=all"):
        raise GitBrokerError("branch creation requires clean working tree")
    current = _git(repo, "symbolic-ref", "--quiet", "--short", "HEAD").strip()
    if current not in ("master", "main"):
        raise GitBrokerError("create task branch from main/master only")
    branch = f"agent/task-{slug}"
    _git(repo, "switch", "-c", branch)
    return branch


def _file(repo: Path, relative: str) -> str:
    from .catalog import valid_path
    if not isinstance(relative, str) or not valid_path(relative):
        raise GitBrokerError("invalid relative file path")
    target = repo / relative
    if target.is_symlink() or not target.is_file() or not target.resolve().is_relative_to(repo):
        raise GitBrokerError("file missing, linked, or outside repository")
    if _git(repo, "ls-files", "--error-unmatch", "--", relative).strip() != relative:
        raise GitBrokerError("only existing tracked files may be staged")
    return relative


def prepare_commit(repo: Path, relative: str) -> dict:
    repo = _root(repo)
    branch = _branch(repo)
    relative = _file(repo, relative)
    if _git(repo, "diff", "--cached", "--name-only"):
        raise GitBrokerError("index must be empty before staging")
    # Explicitly stage one reviewed file; never stage the whole repository.
    _git(repo, "add", "--", relative)
    names = _git(repo, "diff", "--cached", "--name-only").splitlines()
    if names != [relative]:
        raise GitBrokerError("staged file mismatch")
    diff = _git(repo, "diff", "--cached", "--no-ext-diff", "--", relative)
    if not diff:
        raise GitBrokerError("no staged changes")
    fingerprint = hashlib.sha256(diff.encode("utf-8")).hexdigest()
    return {"status": "approval_required", "branch": branch, "path": relative,
            "diff_untrusted": diff, "staged_sha256": fingerprint}


def commit_approved(repo: Path, relative: str, approval: str, message: str) -> dict:
    repo = _root(repo)
    branch = _branch(repo)
    relative = _file(repo, relative)
    if not re.fullmatch(r"[0-9a-f]{64}", approval):
        raise GitBrokerError("invalid approval fingerprint")
    if not isinstance(message, str) or not re.fullmatch(r"[A-Za-z0-9][^\r\n\x00]{0,119}", message):
        raise GitBrokerError("invalid commit message")
    names = _git(repo, "diff", "--cached", "--name-only").splitlines()
    if names != [relative]:
        raise GitBrokerError("only the approved file may be staged")
    diff = _git(repo, "diff", "--cached", "--no-ext-diff", "--", relative)
    if hashlib.sha256(diff.encode("utf-8")).hexdigest() != approval:
        raise GitBrokerError("staged diff changed since approval")
    if _git(repo, "diff", "--", relative):
        raise GitBrokerError("file has unstaged changes")
    # No push. The operator owns the later remote approval step.
    _git(repo, "commit", "-m", message, "--only", "--", relative)
    return {"status": "committed", "branch": branch,
            "commit": _git(repo, "rev-parse", "HEAD").strip(), "path": relative}
