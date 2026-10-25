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
    url = _git(repo, "remote", "get-url", "origin").strip()
    parsed = urlparse(url)
    if (parsed.scheme != "https" or parsed.hostname != "github.com"
            or parsed.username is not None or parsed.password is not None
            or parsed.port is not None or parsed.query or parsed.fragment):
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
    branch = expected["branch"]
    # Avoid invoking repository-defined pre-push hooks. Git credentials must be
    # provisioned separately by the trusted operator, not supplied by the LLM.
    with tempfile.TemporaryDirectory(prefix="swe-empty-hooks-") as hooks:
        result = subprocess.run(
            ["git", "-c", f"core.hooksPath={hooks}", "-C", str(repo),
             "push", "--porcelain", "origin", f"{branch}:refs/heads/{branch}"],
            capture_output=True, text=True, timeout=60, check=False,
            env={k: v for k, v in os.environ.items() if k != "GH_TOKEN"},
        )
    if result.returncode:
        raise GitBrokerError(f"approved branch push failed (exit {result.returncode})")
    payload = json.dumps({"title": title, "body": body,
                          "head": branch, "base": base}).encode("utf-8")
    request = urllib.request.Request(
        f"https://api.github.com/repos/{github_repo}/pulls", data=payload,
        headers={"Authorization": f"Bearer {token}",
                 "Accept": "application/vnd.github+json",
                 "Content-Type": "application/json",
                 "X-GitHub-Api-Version": "2022-11-28",
                 "User-Agent": "secure-swe-agent-a6"}, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            data = json.load(response)
    except urllib.error.HTTPError as exc:
        raise GitBrokerError(f"branch pushed but PR creation failed (HTTP {exc.code})") from None
    except (urllib.error.URLError, TimeoutError, ValueError):
        raise GitBrokerError("branch pushed but PR creation failed; inspect GitHub before retrying") from None
    url = data.get("html_url", "")
    if not isinstance(url, str) or not url.startswith(f"https://github.com/{github_repo}/pull/"):
        raise GitBrokerError("branch pushed but PR response was invalid")
    return {"status": "pull_request_created", "branch": branch,
            "commit": expected["head"], "url": url}
