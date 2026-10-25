"""R3.2 trusted A7 adapter: journal external side effects before executing them.

A workflow left in an in-flight state must be reconciled by an operator. This
module intentionally does not retry external operations automatically.
"""
from __future__ import annotations

import uuid
import hashlib
import os
from pathlib import Path
from typing import Callable

from . import workflow
from .workflow_state import WorkflowStore, StateError


class DurableA7:
    def __init__(self, store: WorkflowStore):
        self.store = store

    def prepare(self, repo: Path, proposal_file: Path, slug: str) -> dict:
        """Journal intent and snapshot immutable proposal before branch creation.

        Artifacts live alongside the operator-owned SQLite DB, never inside the
        agent workspace. Failure after branch creation remains uncertain.
        """
        from .approval import digest, load_proposal
        repo = Path(repo).resolve(strict=True)
        raw = Path(proposal_file).read_bytes()
        load_proposal(raw)
        fingerprint = digest(raw)
        record = self.store.create(repo, fingerprint, preparing=True)
        task_id = record["id"]
        owner = uuid.uuid4().hex
        fence = self.store.acquire_operation(task_id, owner)
        artifacts = self.store.path.parent / (self.store.path.name + ".artifacts")
        try:
            artifacts.mkdir(mode=0o700, exist_ok=True)
            # Exclusive creation prevents replacing another task's evidence.
            target = artifacts / (task_id + ".json")
            with target.open("xb") as output:
                output.write(raw)
                output.flush()
                os.fsync(output.fileno())
            result = workflow.prepare(repo, target, slug)
            completed = self.store.transition(task_id, revision=0,
                                              target="awaiting_apply_approval",
                                              kind="prepare_confirmed")
            return {**result, "workflow_id": task_id,
                    "revision": completed["revision"]}
        except BaseException:
            # The branch may already exist. Never automatically repeat prepare.
            self.store.transition(task_id, revision=0,
                                  target="needs_reconciliation",
                                  kind="prepare_uncertain")
            raise
        finally:
            self.store.release_operation(task_id, owner, fence)

    def proposal_path(self, workflow_id: str) -> Path:
        row = self.store.get(workflow_id)
        path = self.store.path.parent / (self.store.path.name + ".artifacts") / (workflow_id + ".json")
        if path.is_symlink() or not path.is_file():
            raise StateError("immutable proposal artifact missing or linked")
        if hashlib.sha256(path.read_bytes()).hexdigest() != row["proposal_sha256"]:
            raise StateError("immutable proposal artifact changed")
        return path

    def _run(self, workflow_id: str, revision: int, expected: str,
             running: str, success: str, approval: str,
             operation: Callable[[], dict], accepted: set[str]) -> dict:
        row = self.store.get(workflow_id)
        if row["revision"] != revision or row["state"] != expected:
            raise StateError("stale or invalid workflow state")
        # SQLite ownership excludes other coordinators even before the CAS.
        owner = uuid.uuid4().hex
        fence = self.store.acquire_operation(workflow_id, owner)
        try:
            row = self.store.transition(workflow_id, revision=revision, target=running,
                                        approval_sha256=approval,
                                        operation_id=uuid.uuid4().hex)
            try:
                result = operation()
            except BaseException:
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
        finally:
            self.store.release_operation(workflow_id, owner, fence)

    def apply(self, workflow_id: str, revision: int, repo: Path,
              proposal_file: Path, approval: str, enforcer: Path) -> dict:
        row = self.store.get(workflow_id)
        if Path(repo).resolve() != Path(row["repo"]) or approval != row["proposal_sha256"]:
            raise StateError("repository or proposal approval mismatch")
        stored_proposal = self.proposal_path(workflow_id)
        if Path(proposal_file).read_bytes() != stored_proposal.read_bytes():
            raise StateError("supplied proposal differs from immutable artifact")
        return self._run(workflow_id, revision, "awaiting_apply_approval", "applying",
                         "awaiting_commit_approval", approval,
                         lambda: workflow.apply(repo, stored_proposal, approval, enforcer),
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
