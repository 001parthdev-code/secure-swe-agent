"""R3.2 trusted A7 adapter: journal external side effects before executing them.

A workflow left in an in-flight state must be reconciled by an operator. This
module intentionally does not retry external operations automatically.
"""
from __future__ import annotations

import uuid
from pathlib import Path
from typing import Callable

from . import workflow
from .workflow_state import WorkflowStore, StateError


class DurableA7:
    def __init__(self, store: WorkflowStore):
        self.store = store

    def prepare(self, repo: Path, proposal_file: Path, slug: str) -> dict:
        # The branch creation is external; an exception here must not be
        # represented as a successfully prepared workflow.
        result = workflow.prepare(repo, proposal_file, slug)
        record = self.store.create(repo, result["proposal_sha256"])
        return {**result, "workflow_id": record["id"], "revision": record["revision"]}

    def _run(self, workflow_id: str, revision: int, expected: str,
             running: str, success: str, approval: str,
             operation: Callable[[], dict], accepted: set[str]) -> dict:
        row = self.store.get(workflow_id)
        if row["revision"] != revision or row["state"] != expected:
            raise StateError("stale or invalid workflow state")
        # A successful CAS is required before any external side effect.
        row = self.store.transition(workflow_id, revision=revision, target=running,
                                    approval_sha256=approval,
                                    operation_id=uuid.uuid4().hex)
        try:
            result = operation()
        except BaseException:
            # Including KeyboardInterrupt: external outcome may be unknown.
            self.store.transition(workflow_id, revision=row["revision"],
                                  target="needs_reconciliation", kind="operation_exception")
            raise
        if result.get("status") not in accepted:
            target = "verification_failed" if running == "applying" else "needs_reconciliation"
            self.store.transition(workflow_id, revision=row["revision"],
                                  target=target, kind="operation_unconfirmed")
            return {**result, "workflow_id": workflow_id, "state": target}
        finished = self.store.transition(workflow_id, revision=row["revision"],
                                         target=success, kind="operation_confirmed")
        return {**result, "workflow_id": workflow_id,
                "state": finished["state"], "revision": finished["revision"]}

    def apply(self, workflow_id: str, revision: int, repo: Path,
              proposal_file: Path, approval: str, enforcer: Path) -> dict:
        row = self.store.get(workflow_id)
        if Path(repo).resolve() != Path(row["repo"]) or approval != row["proposal_sha256"]:
            raise StateError("repository or proposal approval mismatch")
        return self._run(workflow_id, revision, "awaiting_apply_approval", "applying",
                         "awaiting_commit_approval", approval,
                         lambda: workflow.apply(repo, proposal_file, approval, enforcer),
                         {"verified"})

    def commit(self, workflow_id: str, revision: int, repo: Path, relative: str,
               approval: str, message: str) -> dict:
        row = self.store.get(workflow_id)
        if Path(repo).resolve() != Path(row["repo"]):
            raise StateError("repository mismatch")
        # The underlying broker revalidates the exact staged fingerprint.
        return self._run(workflow_id, revision, "awaiting_commit_approval", "committing",
                         "awaiting_publish_approval", approval,
                         lambda: workflow.commit(repo, relative, approval, message),
                         {"committed"})

    def publish(self, workflow_id: str, revision: int, repo: Path, github_repo: str,
                base: str, title: str, body: str, approval: str) -> dict:
        row = self.store.get(workflow_id)
        if Path(repo).resolve() != Path(row["repo"]):
            raise StateError("repository mismatch")
        # Publishing broker rechecks approval and remote state; no blind retries.
        return self._run(workflow_id, revision, "awaiting_publish_approval", "publishing",
                         "published", approval,
                         lambda: workflow.publish(repo, github_repo, base, title, body, approval),
                         {"pull_request_created", "pull_request_exists"})
