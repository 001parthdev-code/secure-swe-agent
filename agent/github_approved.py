"""Trusted operator CLI: review publishing plan, then explicitly approve."""
import argparse
import json
import subprocess
import sys
from pathlib import Path
from secure_swe_agent.git_broker import GitBrokerError
from secure_swe_agent.github_broker import preview_publish, publish_approved


def main():
    parser = argparse.ArgumentParser(description="Operator-approved GitHub publishing")
    parser.add_argument("--repo", required=True, type=Path)
    parser.add_argument("--github-repo", required=True, help="owner/repository")
    parser.add_argument("--base", choices=["main", "master"], default="master")
    sub = parser.add_subparsers(dest="action", required=True)
    preview = sub.add_parser("preview")
    preview.add_argument("--title", required=True)
    preview.add_argument("--body", default="Proposed and verified changes; human-approved publication.")
    publish = sub.add_parser("publish")
    publish.add_argument("--approve-sha256", required=True)
    publish.add_argument("--title", required=True)
    publish.add_argument("--body", default="Proposed and verified changes; human-approved publication.")
    args = parser.parse_args()
    try:
        if args.action == "preview":
            output = preview_publish(args.repo, args.github_repo, args.base, title=args.title, body=args.body)
        else:
            output = publish_approved(args.repo, args.github_repo, args.approve_sha256,
                                      base=args.base, title=args.title, body=args.body)
        print(json.dumps(output, indent=2))
        return 0
    except (GitBrokerError, OSError, subprocess.TimeoutExpired) as exc:
        print(json.dumps({"status": "rejected", "reason": str(exc)}), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
