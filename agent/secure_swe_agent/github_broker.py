"""A6 operator-only GitHub publishing. Not callable by model-generated tool requests.

Only use with a trusted repository and operator-controlled Git configuration.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import tempfile
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import urlparse

from .git_broker import GitBrokerError, _branch, _git, _root


_SLUG = re.compile(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+\Z")
_SHA = re.compile(r"[0-9a-f]{64}\Z")


def _origin(repo: Path, expected: str) -> str:
    if not _SLUG.fullmatch(expected) or ".." in expected:
        raise GitBrokerError("invalid GitHub repository slug")
    # Read the configured URL, not Git's transport-rewritten get-url result.
    url = _git(repo, "config", "--local", "--get", "remote.origin.url").strip()
    parsed = urlparse(url)
    if (parsed.scheme != "https" or parsed.hostname != "github.com"
            or parsed.username is not None or parsed.password is not None
            or parsed.port is not None or parsed.query or parsed.fragment
            or parsed.params or parsed.path.endswith("/") or parsed.path.count("/") != 2):
        raise GitBrokerError("origin must be a credential-free HTTPS github.com URL")
    path = parsed.path.removeprefix("/").removesuffix(".git")
    if path != expected:
        raise GitBrokerError("origin does not match approved repository")
    return url


def _plan(repo: Path, github_repo: str, base: str, title: str, body: str) -> dict:
    if (not isinstance(title, str) or not 1 <= len(title) <= 120
            or any(c in title for c in "\r\n\x00")):
        raise GitBrokerError("invalid pull request title")
    if not isinstance(body, str) or len(body) > 8000 or "\x00" in body:
        raise GitBrokerError("invalid pull request body")
    repo = _root(repo)
    branch = _branch(repo)
    if base not in ("main", "master"):
        raise GitBrokerError("base branch must be main or master")
    _origin(repo, github_repo)
    if _git(repo, "status", "--porcelain", "--untracked-files=all"):
        raise GitBrokerError("publishing requires a clean working tree")
    head = _git(repo, "rev-parse", "HEAD").strip()
    if not re.fullmatch(r"[0-9a-f]{40,64}", head):
        raise GitBrokerError("invalid commit identifier")
    return {"github_repo": github_repo, "branch": branch, "head": head, "base": base,
            "title": title, "body": body}


def preview_publish(repo: Path, github_repo: str, base: str = "master", *,
                    title: str, body: str) -> dict:
    plan = _plan(repo, github_repo, base, title, body)
    encoded = json.dumps(plan, sort_keys=True, separators=(",", ":")).encode()
    return {"status": "approval_required", **plan,
            "approval_sha256": hashlib.sha256(encoded).hexdigest(),
            "warning": "Publishing pushes this commit to GitHub and creates a PR; review before approving."}


def _github_request(url: str, token: str, *, payload: bytes | None = None):
    headers = {"Authorization": f"Bearer {token}",
               "Accept": "application/vnd.github+json",
               "X-GitHub-Api-Version": "2022-11-28",
               "User-Agent": "secure-swe-agent-a6"}
    if payload is not None:
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(url, data=payload, headers=headers,
                                     method="POST" if payload is not None else "GET")
    with urllib.request.urlopen(request, timeout=20) as response:
        return json.load(response)


def _existing_pr(github_repo: str, branch: str, base: str, head: str,
                 title: str, body: str, token: str) -> dict | None:
    from urllib.parse import urlencode
    owner = github_repo.split("/", 1)[0]
    query = urlencode({"state": "open", "head": f"{owner}:{branch}", "base": base,
                       "per_page": "100"})
    data = _github_request(f"https://api.github.com/repos/{github_repo}/pulls?{query}", token)
    if not isinstance(data, list):
        raise GitBrokerError("unexpected GitHub PR lookup response")
    for pr in data:
        if not isinstance(pr, dict):
            continue
        remote_head = pr.get("head") or {}
        remote_base = pr.get("base") or {}
        if (remote_head.get("sha") == head
                and remote_head.get("ref") == branch
                and remote_base.get("ref") == base
                and pr.get("title") == title
                and pr.get("body") == body):
            url = pr.get("html_url", "")
            if isinstance(url, str) and re.fullmatch(
                    rf"https://github\.com/{re.escape(github_repo)}/pull/[0-9]+", url):
                return {"status": "pull_request_exists", "branch": branch,
                        "commit": head, "url": url}
        # A PR with the same head/base but different approved content is a conflict.
        if remote_head.get("ref") == branch and remote_base.get("ref") == base:
            raise GitBrokerError("existing PR does not match approved commit or metadata")
    return None


def _remote_head(repo: Path, branch: str) -> str | None:
    output = _git(repo, "ls-remote", "--heads", "origin", f"refs/heads/{branch}")
    if not output.strip():
        return None
    lines = output.splitlines()
    if len(lines) != 1:
        raise GitBrokerError("ambiguous remote task branch")
    sha, ref = lines[0].split("\t", 1)
    if ref != f"refs/heads/{branch}" or not re.fullmatch(r"[0-9a-f]{40,64}", sha):
        raise GitBrokerError("unexpected remote task branch response")
    return sha


def _push_guard(repo: Path, branch: str) -> None:
    with tempfile.TemporaryDirectory(prefix="swe-empty-hooks-") as hooks:
        result = subprocess.run(
            ["git", "-c", f"core.hooksPath={hooks}", "-C", str(repo),
             "push", "--porcelain", "origin", f"{branch}:refs/heads/{branch}"],
            capture_output=True, text=True, timeout=60, check=False,
            env={k: v for k, v in os.environ.items() if k != "GH_TOKEN"},
        )
    if result.returncode:
        raise GitBrokerError(f"approved branch push failed (exit {result.returncode})")


def publish_approved(repo: Path, github_repo: str, approval: str, *,
                     base: str = "master", title: str, body: str) -> dict:
    if not isinstance(approval, str) or not _SHA.fullmatch(approval):
        raise GitBrokerError("invalid approval fingerprint")
    expected = preview_publish(repo, github_repo, base, title=title, body=body)
    if approval != expected["approval_sha256"]:
        raise GitBrokerError("repository, branch, commit or base changed since approval")
    token = os.environ.get("GH_TOKEN")
    if not token:
        raise GitBrokerError("GH_TOKEN required for PR creation; never provide it to the model")
    repo = _root(repo)
    branch, head = expected["branch"], expected["head"]

    # Check remote state before any write. Never overwrite a differing branch.
    try:
        remote = _remote_head(repo, branch)
    except (GitBrokerError, subprocess.TimeoutExpired) as exc:
        raise GitBrokerError(f"cannot verify remote branch: {exc}") from None
    if remote is not None and remote != head:
        raise GitBrokerError("remote branch differs from approved commit; refusing push")
    try:
        existing = _existing_pr(github_repo, branch, base, head, title, body, token)
    except urllib.error.HTTPError as exc:
        raise GitBrokerError(f"GitHub PR lookup failed (HTTP {exc.code}); no push attempted") from None
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError):
        raise GitBrokerError("GitHub PR lookup unavailable; no push attempted") from None
    if existing is not None:
        if remote != head:
            raise GitBrokerError("PR exists but remote branch is not at approved commit")
        return existing

    if remote is None:
        # Do not invoke repository-defined pre-push hooks. The remote is trusted
        # operator configuration; no model-controlled credentials are passed.
        _push_guard(repo, branch)
    # A successful push is not enough: verify the remote ref before opening a PR.
    try:
        if _remote_head(repo, branch) != head:
            raise GitBrokerError("remote branch does not match approved commit after push")
    except subprocess.TimeoutExpired:
        raise GitBrokerError("branch may be pushed; remote verification timed out") from None

    payload = json.dumps({"title": title, "body": body,
                          "head": branch, "base": base}).encode("utf-8")
    try:
        data = _github_request(f"https://api.github.com/repos/{github_repo}/pulls",
                               token, payload=payload)
    except urllib.error.HTTPError as exc:
        # GitHub may return 422 if a PR was created by an earlier attempt.
        if exc.code == 422:
            try:
                existing = _existing_pr(github_repo, branch, base, head, title, body, token)
                if existing is not None:
                    return existing
            except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, ValueError):
                pass
        raise GitBrokerError(f"branch pushed but PR creation failed (HTTP {exc.code}); retry only after checking GitHub") from None
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError):
        raise GitBrokerError("branch pushed but PR creation uncertain; inspect GitHub before retrying") from None
    url = data.get("html_url", "") if isinstance(data, dict) else ""
    if not isinstance(url, str) or not re.fullmatch(
            rf"https://github\.com/{re.escape(github_repo)}/pull/[0-9]+", url):
        raise GitBrokerError("branch pushed but PR response was invalid")
    return {"status": "pull_request_created", "branch": branch,
            "commit": head, "url": url}
