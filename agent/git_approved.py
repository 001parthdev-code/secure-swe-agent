"""Operator-only CLI for local supervised Git operations (A5)."""
import argparse
import json
import sys
import subprocess
from pathlib import Path
from secure_swe_agent.git_broker import (
    GitBrokerError, create_task_branch, prepare_commit, commit_approved,
)


def main():
    p = argparse.ArgumentParser(description="Local supervised Git broker; never pushes")
    p.add_argument("--repo", type=Path, required=True)
    commands = p.add_subparsers(dest="action", required=True)
    branch = commands.add_parser("branch")
    branch.add_argument("--slug", required=True)
    prepare = commands.add_parser("prepare")
    prepare.add_argument("--file", required=True)
    commit = commands.add_parser("commit")
    commit.add_argument("--file", required=True)
    commit.add_argument("--approve-sha256", required=True)
    commit.add_argument("--message", required=True)
    args = p.parse_args()
    try:
        if args.action == "branch":
            result = {"status": "created", "branch": create_task_branch(args.repo, args.slug)}
        elif args.action == "prepare":
            result = prepare_commit(args.repo, args.file)
        else:
            result = commit_approved(args.repo, args.file, args.approve_sha256, args.message)
        print(json.dumps(result, indent=2))
        return 0
    except (GitBrokerError, OSError, subprocess.TimeoutExpired) as exc:
        print(json.dumps({"status": "rejected", "reason": str(exc)}), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
