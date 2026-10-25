"""R3.4 cross-process exclusion and non-replaying evidence checks."""
import hashlib
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from secure_swe_agent.workflow_state import WorkflowStore, StateError
from secure_swe_agent.durable_a7 import DurableA7
from secure_swe_agent.recovery_evidence import filesystem_evidence


class OwnershipTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.repo = self.root / "repo"
        self.repo.mkdir()
        self.store = WorkflowStore(self.root / "journal.db")
        self.addCleanup(self.store.close)
        self.task = self.store.create(self.repo, "a" * 64)

    def test_second_connection_cannot_claim_same_task(self):
        fence = self.store.acquire_operation(self.task["id"], "operator-one")
        with WorkflowStore(self.store.path) as other:
            with self.assertRaisesRegex(StateError, "already owned"):
                other.acquire_operation(self.task["id"], "operator-two")
            with self.assertRaisesRegex(StateError, "ownership mismatch"):
                other.release_operation(self.task["id"], "operator-two", fence)
        self.store.release_operation(self.task["id"], "operator-one", fence)
        with WorkflowStore(self.store.path) as other:
            other.acquire_operation(self.task["id"], "operator-two")

    def test_expired_owner_is_not_stolen_or_recovered(self):
        self.store.transition(self.task["id"], revision=0, target="applying",
                              approval_sha256="b" * 64, operation_id="op")
        self.store.acquire_operation(self.task["id"], "operator-one", ttl=1)
        self.store.db.execute("UPDATE operation_owners SET expires_at=0")
        with WorkflowStore(self.store.path) as other:
            self.assertEqual(other.recover(), [])
            with self.assertRaisesRegex(StateError, "already owned"):
                other.acquire_operation(self.task["id"], "operator-two")
        self.assertEqual(self.store.get(self.task["id"])["state"], "applying")

    def test_crash_before_completion_never_replays(self):
        calls = []
        def operation():
            calls.append("executed")
            raise KeyboardInterrupt()
        with self.assertRaises(KeyboardInterrupt):
            DurableA7(self.store)._run(self.task["id"], 0,
                "awaiting_apply_approval", "applying", "awaiting_commit_approval",
                "b" * 64, operation, {"verified"})
        self.assertEqual(calls, ["executed"])
        self.assertEqual(self.store.get(self.task["id"])["state"], "needs_reconciliation")
        with self.assertRaises(StateError):
            DurableA7(self.store)._run(self.task["id"], 0,
                "awaiting_apply_approval", "applying", "awaiting_commit_approval",
                "b" * 64, operation, {"verified"})
        self.assertEqual(calls, ["executed"])

    def test_filesystem_evidence_is_read_only_and_not_resolution(self):
        self.store.transition(self.task["id"], revision=0, target="applying",
                              approval_sha256="b" * 64, operation_id="op")
        self.store.recover()
        path = self.repo / "fixed.py"
        path.write_bytes(b"correct")
        digest = hashlib.sha256(b"correct").hexdigest()
        result = filesystem_evidence(self.store, self.task["id"], "fixed.py", digest)
        self.assertTrue(result["matches"])
        self.assertEqual(self.store.get(self.task["id"])["state"], "needs_reconciliation")
        with self.assertRaisesRegex(StateError, "invalid evidence path"):
            filesystem_evidence(self.store, self.task["id"], "../outside", digest)

if __name__ == "__main__":
    unittest.main()
