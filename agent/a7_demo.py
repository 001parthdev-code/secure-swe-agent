"""Operator CLI for the A7 controlled calculator demonstration."""
import argparse
import json
import sys
from pathlib import Path
from secure_swe_agent.workflow import (WorkflowError, prepare, apply, review_commit,
                                       commit, review_publish, publish)
from secure_swe_agent.approval import ApprovalError
from secure_swe_agent.git_broker import GitBrokerError
from secure_swe_agent.enforcer import EnforcerError


def main():
    p = argparse.ArgumentParser(description="A7 supervised demonstration (trusted calculator only)")
    p.add_argument("--repo", type=Path, required=True)
    sub = p.add_subparsers(dest="action", required=True)
    a = sub.add_parser("prepare")
    a.add_argument("--proposal", type=Path, required=True)
    a.add_argument("--slug", required=True)
    a = sub.add_parser("apply")
    a.add_argument("--proposal", type=Path, required=True)
    a.add_argument("--approve-sha256", required=True)
    a.add_argument("--enforcer", type=Path, required=True)
    a = sub.add_parser("review-commit")
    a = sub.add_parser("commit")
    a.add_argument("--approve-sha256", required=True)
    a.add_argument("--message", required=True)
    for action in ("review-publish", "publish"):
        a = sub.add_parser(action)
        a.add_argument("--github-repo", required=True)
        a.add_argument("--base", choices=("main", "master"), default="master")
        a.add_argument("--title", required=True)
        a.add_argument("--body", default="Verified calculator correction")
        if action == "publish":
            a.add_argument("--approve-sha256", required=True)
    args = p.parse_args()
    repo = args.repo
    relative = "workspace/calculator/calculator.py"
    try:
        if args.action == "prepare":
            result = prepare(repo, args.proposal, args.slug)
        elif args.action == "apply":
            if sys.platform != "linux":
                raise WorkflowError("E2 application requires Linux")
            result = apply(repo, args.proposal, args.approve_sha256, args.enforcer)
        elif args.action == "review-commit":
            result = review_commit(repo, relative)
        elif args.action == "commit":
            result = commit(repo, relative, args.approve_sha256, args.message)
        elif args.action == "review-publish":
            result = review_publish(repo, args.github_repo, args.base, args.title, args.body)
        else:
            result = publish(repo, args.github_repo, args.base, args.title, args.body,
                             args.approve_sha256)
        print(json.dumps(result, indent=2))
        return 0 if result.get("status") not in ("apply_failed", "verification_failed", "stale_proposal") else 1
    except (WorkflowError, ApprovalError, GitBrokerError, EnforcerError, OSError, ValueError) as exc:
        print(json.dumps({"status": "rejected", "reason": str(exc)}), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
