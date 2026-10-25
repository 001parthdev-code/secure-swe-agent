"""Operator-only durable A7 CLI for the trusted calculator demonstration.

The journal is not a security boundary. It must live outside agent-writable paths.
An uncertain operation is never automatically replayed.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from secure_swe_agent import workflow
from secure_swe_agent.durable_a7 import DurableA7
from secure_swe_agent.workflow_state import StateError, WorkflowStore
from secure_swe_agent.git_broker import GitBrokerError
from secure_swe_agent.approval import ApprovalError
from secure_swe_agent.enforcer import EnforcerError
from secure_swe_agent.recovery_evidence import filesystem_evidence, git_evidence, github_evidence

RELATIVE = "workspace/calculator/calculator.py"


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Durable A7 operator CLI (trusted calculator only)")
    p.add_argument("--db", required=True, type=Path, help="SQLite path outside the agent workspace")
    sub = p.add_subparsers(dest="action", required=True)
    a = sub.add_parser("prepare")
    a.add_argument("--repo", required=True, type=Path)
    a.add_argument("--proposal", required=True, type=Path)
    a.add_argument("--slug", required=True)
    for name in ("status", "events", "apply", "review-commit", "commit", "review-publish", "publish"):
        a = sub.add_parser(name)
        a.add_argument("--id", required=True)
        if name in ("apply", "commit", "publish"):
            a.add_argument("--revision", required=True, type=int)
        if name == "apply":
            a.add_argument("--proposal", required=True, type=Path)
            a.add_argument("--approve-sha256", required=True)
            a.add_argument("--enforcer", required=True, type=Path)
        if name == "commit":
            a.add_argument("--approve-sha256", required=True)
            a.add_argument("--message", required=True)
        if name in ("review-publish", "publish"):
            a.add_argument("--github-repo", required=True)
            a.add_argument("--base", choices=("main", "master"), default="main")
            a.add_argument("--title", required=True)
            a.add_argument("--body", default="Verified calculator correction")
            if name == "publish":
                a.add_argument("--approve-sha256", required=True)
    sub.add_parser("recover").add_argument("--confirm-no-active-operations", action="store_true")
    for name in ("recovery-inspect", "recovery-quarantine", "recovery-filesystem", "recovery-git", "recovery-github"):
        a = sub.add_parser(name)
        a.add_argument("--id", required=True)
        if name == "recovery-quarantine":
            a.add_argument("--owner", required=True)
            a.add_argument("--fence", required=True, type=int)
            a.add_argument("--confirmed-stopped", action="store_true")
        if name == "recovery-filesystem":
            a.add_argument("--relative", required=True)
            a.add_argument("--expected-sha256", required=True)
        if name in ("recovery-git", "recovery-github"):
            a.add_argument("--expected-commit", required=True)
        if name == "recovery-github":
            a.add_argument("--github-repo", required=True)
            a.add_argument("--branch", required=True)
            a.add_argument("--base", choices=("main", "master"), required=True)
            a.add_argument("--title", required=True)
            a.add_argument("--body", required=True)
    return p


def execute(args: argparse.Namespace, store: WorkflowStore) -> dict:
    durable = DurableA7(store)
    if args.action == "prepare":
        return durable.prepare(args.repo, args.proposal, args.slug)
    if args.action == "recover":
        if not args.confirm_no_active_operations:
            raise StateError("stop all other coordinators before recovery")
        return {"status": "reconciliation_required", "workflows": store.recover()}
    row = store.get(args.id)
    if args.action == "recovery-inspect":
        return {"status": "inspection_only", "workflow": row,
                "operation_owner": store.operation_owner(args.id),
                "events": store.events(args.id)}
    if args.action == "recovery-quarantine":
        # The flag is a human assertion, not proof of process termination.
        # Never expose this operator-only action to an agent or web client.
        updated = store.quarantine_abandoned_owner(
            args.id, owner=args.owner, fence=args.fence,
            confirmed_stopped=args.confirmed_stopped)
        return {"status": "needs_reconciliation", "workflow": updated,
                "warning": "External outcome remains unverified; no replay or state resolution."}
    if args.action == "recovery-filesystem":
        return filesystem_evidence(store, args.id, args.relative, args.expected_sha256)
    if args.action == "recovery-git":
        return git_evidence(store, args.id, args.expected_commit)
    if args.action == "recovery-github":
        import os
        token = os.environ.get("GH_TOKEN")
        if not token:
            raise StateError("GH_TOKEN required for read-only GitHub evidence")
        return github_evidence(store, args.id, github_repo=args.github_repo,
                               branch=args.branch, expected_commit=args.expected_commit,
                               base=args.base, title=args.title, body=args.body, token=token)
    if args.action == "status":
        return {"status": "ok", "workflow": row}
    if args.action == "events":
        return {"status": "ok", "events": store.events(args.id)}
    repo = Path(row["repo"])
    if row["state"] == "needs_reconciliation":
        raise StateError("external outcome uncertain; operator reconciliation required")
    if args.action == "apply":
        if sys.platform != "linux":
            raise StateError("E2 application requires Linux")
        return durable.apply(args.id, args.revision, repo, args.proposal,
                             args.approve_sha256, args.enforcer)
    if args.action == "review-commit":
        if row["state"] != "awaiting_commit_approval":
            raise StateError("commit review not available in current state")
        return workflow.review_commit(repo, RELATIVE)
    if args.action == "commit":
        return durable.commit(args.id, args.revision, repo, RELATIVE,
                              args.approve_sha256, args.message)
    if args.action == "review-publish":
        if row["state"] != "awaiting_publish_approval":
            raise StateError("publish review not available in current state")
        return workflow.review_publish(repo, args.github_repo, args.base,
                                       args.title, args.body)
    if args.action == "publish":
        return durable.publish(args.id, args.revision, repo, args.github_repo,
                               args.base, args.title, args.body, args.approve_sha256)
    raise StateError("unsupported operation")


def main() -> int:
    args = parser().parse_args()
    try:
        with WorkflowStore(args.db) as store:
            result = execute(args, store)
        print(json.dumps(result, indent=2))
        return 0
    except (StateError, GitBrokerError, ApprovalError, EnforcerError,
            workflow.WorkflowError, OSError, ValueError) as exc:
        print(json.dumps({"status": "rejected", "reason": str(exc)}), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
