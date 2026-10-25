"""R3.3 operator CLI state and restart tests; no external side effects."""
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import a7_durable
from secure_swe_agent.workflow_state import StateError, WorkflowStore


class DurableCliTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.db = self.root / "journal.sqlite"
        self.repo = self.root / "repo"
        self.repo.mkdir()

    def test_restart_retains_identity_and_events(self):
        with WorkflowStore(self.db) as store:
            row = store.create(self.repo, "a" * 64)
            task_id = row["id"]
        args = a7_durable.parser().parse_args(["--db", str(self.db), "status", "--id", task_id])
        with WorkflowStore(self.db) as store:
            result = a7_durable.execute(args, store)
            self.assertEqual(result["workflow"]["id"], task_id)
            self.assertEqual(result["workflow"]["state"], "awaiting_apply_approval")

    def test_recovery_requires_operator_confirmation(self):
        args = a7_durable.parser().parse_args(["--db", str(self.db), "recover"])
        with WorkflowStore(self.db) as store:
            with self.assertRaisesRegex(StateError, "stop all other"):
                a7_durable.execute(args, store)

    def test_recovered_uncertain_operation_is_not_replayed(self):
        with WorkflowStore(self.db) as store:
            row = store.create(self.repo, "b" * 64)
            row = store.transition(row["id"], revision=0, target="applying",
                                   approval_sha256="b" * 64, operation_id="op")
            task_id = row["id"]
        args = a7_durable.parser().parse_args([
            "--db", str(self.db), "recover", "--confirm-no-active-operations"])
        with WorkflowStore(self.db) as store:
            result = a7_durable.execute(args, store)
            self.assertEqual(result["workflows"][0]["state"], "needs_reconciliation")
        apply_args = a7_durable.parser().parse_args([
            "--db", str(self.db), "apply", "--id", task_id, "--revision", "2",
            "--proposal", str(self.root / "missing.json"),
            "--approve-sha256", "b" * 64, "--enforcer", str(self.root / "missing")])
        with WorkflowStore(self.db) as store:
            with patch.object(a7_durable.sys, "platform", "linux"):
                with self.assertRaisesRegex(StateError, "uncertain"):
                    a7_durable.execute(apply_args, store)

    def test_review_does_not_run_in_wrong_state(self):
        with WorkflowStore(self.db) as store:
            row = store.create(self.repo, "c" * 64)
            args = a7_durable.parser().parse_args([
                "--db", str(self.db), "review-commit", "--id", row["id"]])
            with self.assertRaisesRegex(StateError, "not available"):
                a7_durable.execute(args, store)


if __name__ == "__main__":
    unittest.main()
