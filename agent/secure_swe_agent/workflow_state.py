"""R3 durable workflow journal. No security-sensitive side effects are executed here.

The journal records intent and outcomes; it never infers external success from a
previous attempt. Only a trusted coordinator may invoke transitions.
"""
from __future__ import annotations

import json
import re
import sqlite3
import time
import uuid
from pathlib import Path


class StateError(ValueError):
    pass


_STATES = {
    "awaiting_apply_approval", "applying", "awaiting_commit_approval",
    "committing", "awaiting_publish_approval", "publishing", "published",
    "verification_failed", "needs_reconciliation", "cancelled",
}
_TRANSITIONS = {
    "awaiting_apply_approval": {"applying", "cancelled"},
    "applying": {"awaiting_commit_approval", "verification_failed", "needs_reconciliation"},
    "awaiting_commit_approval": {"committing", "cancelled"},
    "committing": {"awaiting_publish_approval", "needs_reconciliation"},
    "awaiting_publish_approval": {"publishing", "cancelled"},
    "publishing": {"published", "needs_reconciliation"},
    "needs_reconciliation": {"awaiting_commit_approval", "awaiting_publish_approval", "published", "verification_failed"},
    "verification_failed": {"cancelled"},
    "published": set(),
    "cancelled": set(),
}
_IN_FLIGHT = {"applying", "committing", "publishing"}
_HASH = re.compile(r"[0-9a-f]{64}\Z")


class WorkflowStore:
    """SQLite-backed, single-host workflow state; external operations stay outside DB locks.

    Use a database outside the agent-writable workspace. The DB must be writable
    only by the trusted coordinator. SQLite is not an authorization boundary.
    """

    def __init__(self, path: Path):
        self.path = Path(path)
        if not self.path.parent.is_dir():
            raise StateError("database parent directory does not exist")
        self.db = sqlite3.connect(str(self.path), timeout=5, isolation_level=None)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA busy_timeout=5000")
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("PRAGMA foreign_keys=ON")
        self.db.executescript("""
            CREATE TABLE IF NOT EXISTS workflows (
                id TEXT PRIMARY KEY, repo TEXT NOT NULL, state TEXT NOT NULL,
                revision INTEGER NOT NULL, proposal_sha256 TEXT NOT NULL,
                approval_sha256 TEXT, operation_id TEXT,
                updated_at INTEGER NOT NULL
            );
            CREATE TABLE IF NOT EXISTS events (
                workflow_id TEXT NOT NULL, revision INTEGER NOT NULL,
                state TEXT NOT NULL, kind TEXT NOT NULL, detail TEXT NOT NULL,
                created_at INTEGER NOT NULL,
                PRIMARY KEY(workflow_id, revision),
                FOREIGN KEY(workflow_id) REFERENCES workflows(id)
            );
        """)

    def close(self):
        self.db.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()

    def _begin(self):
        self.db.execute("BEGIN IMMEDIATE")

    def _rollback(self):
        self.db.execute("ROLLBACK")

    def create(self, repo: Path, proposal_sha256: str) -> dict:
        if not isinstance(proposal_sha256, str) or not _HASH.fullmatch(proposal_sha256):
            raise StateError("invalid proposal digest")
        repo = Path(repo).resolve(strict=True)
        if not repo.is_dir():
            raise StateError("repository must be a directory")
        workflow_id = uuid.uuid4().hex
        now = int(time.time())
        self._begin()
        try:
            self.db.execute("INSERT INTO workflows VALUES (?,?,?,?,?,?,?,?)",
                            (workflow_id, str(repo), "awaiting_apply_approval", 0,
                             proposal_sha256, None, None, now))
            self.db.execute("INSERT INTO events VALUES (?,?,?,?,?,?)",
                            (workflow_id, 0, "awaiting_apply_approval", "created", "{}", now))
            self.db.execute("COMMIT")
        except Exception:
            self._rollback()
            raise
        return self.get(workflow_id)

    def get(self, workflow_id: str) -> dict:
        row = self.db.execute("SELECT * FROM workflows WHERE id=?", (workflow_id,)).fetchone()
        if row is None:
            raise StateError("unknown workflow")
        return dict(row)

    def events(self, workflow_id: str) -> list[dict]:
        self.get(workflow_id)
        return [dict(row) for row in self.db.execute(
            "SELECT * FROM events WHERE workflow_id=? ORDER BY revision", (workflow_id,))]

    def transition(self, workflow_id: str, *, revision: int, target: str,
                   approval_sha256: str | None = None,
                   operation_id: str | None = None, kind: str = "transition") -> dict:
        """CAS transition. Repeated requests with stale revision are rejected.

        In-flight operations require a stable operation ID for reconciliation.
        Approval hashes are recorded only; trusted caller verifies their binding.
        """
        if target not in _STATES:
            raise StateError("unknown target state")
        if approval_sha256 is not None and not _HASH.fullmatch(approval_sha256):
            raise StateError("invalid approval digest")
        if target in _IN_FLIGHT and (not operation_id or len(operation_id) > 128):
            raise StateError("in-flight operation requires operation ID")
        self._begin()
        try:
            row = self.db.execute("SELECT * FROM workflows WHERE id=?", (workflow_id,)).fetchone()
            if row is None:
                raise StateError("unknown workflow")
            if row["revision"] != revision:
                raise StateError("stale workflow revision")
            if target not in _TRANSITIONS[row["state"]]:
                raise StateError("invalid workflow transition")
            if target in _IN_FLIGHT and approval_sha256 is None:
                raise StateError("approval digest required for sensitive operation")
            next_rev = revision + 1
            now = int(time.time())
            self.db.execute("""UPDATE workflows SET state=?, revision=?, approval_sha256=?,
                              operation_id=?, updated_at=? WHERE id=?""",
                            (target, next_rev, approval_sha256, operation_id, now, workflow_id))
            self.db.execute("INSERT INTO events VALUES (?,?,?,?,?,?)",
                            (workflow_id, next_rev, target, kind, "{}", now))
            self.db.execute("COMMIT")
        except Exception:
            self._rollback()
            raise
        return self.get(workflow_id)

    def recover(self) -> list[dict]:
        """Mark interrupted side effects uncertain. Never replay them automatically."""
        self._begin()
        try:
            rows = self.db.execute("SELECT id, revision FROM workflows WHERE state IN (?,?,?)",
                                   tuple(sorted(_IN_FLIGHT))).fetchall()
            for row in rows:
                now = int(time.time())
                rev = row["revision"] + 1
                self.db.execute("""UPDATE workflows SET state='needs_reconciliation',
                                  revision=?, updated_at=? WHERE id=?""", (rev, now, row["id"]))
                self.db.execute("INSERT INTO events VALUES (?,?,?,?,?,?)",
                                (row["id"], rev, "needs_reconciliation", "restart", "{}", now))
            self.db.execute("COMMIT")
        except Exception:
            self._rollback()
            raise
        return [self.get(row["id"]) for row in rows]
