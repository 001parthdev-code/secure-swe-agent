"""R3.4.4 real process termination and operator-only recovery CLI tests."""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import a7_durable
from secure_swe_agent.workflow_state import StateError, WorkflowStore


class CrashRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.repo = self.root / "repo"
        self.repo.mkdir()
        self.db = self.root / "state.sqlite"
        with WorkflowStore(self.db) as store:
            self.task = store.create(self.repo, "a" * 64)["id"]

    def run_cli(self, *args):
        parsed = a7_durable.parser().parse_args(["--db", str(self.db), *args])
        with WorkflowStore(self.db) as store:
            return a7_durable.execute(parsed, store)

    def test_real_crash_keeps_ownership_and_never_replays(self):
        # A distinct OS process acquires ownership and exits abruptly without
        # finally/cleanup. No child executes an external side effect.
        code = 'import os, sys\nsys.path.insert(0, sys.argv[3])\nfrom secure_swe_agent.workflow_state import WorkflowStore\nwith WorkflowStore(sys.argv[1]) as store:\n    store.acquire_operation(sys.argv[2], "crashed-coordinator")\nos._exit(77)\n'
        agent_dir = str(Path(__file__).resolve().parents[1])
        result = subprocess.run([sys.executable, "-c", code, str(self.db),
                                 self.task, agent_dir], check=False, timeout=10)
        self.assertEqual(result.returncode, 77)
        with WorkflowStore(self.db) as store:
            lock = store.operation_owner(self.task)
            self.assertEqual(lock["owner"], "crashed-coordinator")
            with self.assertRaisesRegex(StateError, "already owned"):
                store.acquire_operation(self.task, "second-coordinator")
        inspected = self.run_cli("recovery-inspect", "--id", self.task)
        self.assertEqual(inspected["operation_owner"]["owner"], "crashed-coordinator")
        with self.assertRaisesRegex(StateError, "termination confirmation"):
            self.run_cli("recovery-quarantine", "--id", self.task,
                         "--owner", "crashed-coordinator", "--fence", str(lock["fencing"]))
        # This task is not in-flight; quarantine must reject even with a human
        # assertion, preventing arbitrary removal of live-task ownership.
        with self.assertRaisesRegex(StateError, "outside uncertain"):
            self.run_cli("recovery-quarantine", "--id", self.task,
                         "--owner", "crashed-coordinator", "--fence", str(lock["fencing"]),
                         "--confirmed-stopped")

    def test_crash_during_inflight_requires_explicit_quarantine(self):
        with WorkflowStore(self.db) as store:
            store.transition(self.task, revision=0, target="applying",
                             approval_sha256="b" * 64, operation_id="op")
        code = 'import os, sys\nsys.path.insert(0, sys.argv[3])\nfrom secure_swe_agent.workflow_state import WorkflowStore\nwith WorkflowStore(sys.argv[1]) as store:\n    store.acquire_operation(sys.argv[2], "crashed-coordinator")\nos._exit(78)\n'
        agent_dir = str(Path(__file__).resolve().parents[1])
        result = subprocess.run([sys.executable, "-c", code, str(self.db),
                                 self.task, agent_dir], check=False, timeout=10)
        self.assertEqual(result.returncode, 78)
        with WorkflowStore(self.db) as store:
            lock = store.operation_owner(self.task)
        with self.assertRaises(StateError):
            self.run_cli("recovery-quarantine", "--id", self.task,
                         "--owner", "wrong", "--fence", str(lock["fencing"]),
                         "--confirmed-stopped")
        outcome = self.run_cli("recovery-quarantine", "--id", self.task,
                               "--owner", "crashed-coordinator", "--fence", str(lock["fencing"]),
                               "--confirmed-stopped")
        self.assertEqual(outcome["workflow"]["state"], "needs_reconciliation")
        evidence = self.run_cli("recovery-filesystem", "--id", self.task,
                                "--relative", "missing.py", "--expected-sha256", "c" * 64)
        self.assertEqual(evidence["outcome"], "missing")
        self.assertEqual(self.run_cli("status", "--id", self.task)["workflow"]["state"],
                         "needs_reconciliation")
        with WorkflowStore(self.db) as store:
            with self.assertRaisesRegex(StateError, "reconciliation"):
                store.acquire_operation(self.task, "new-coordinator")

    def test_github_evidence_requires_token_before_network(self):
        with WorkflowStore(self.db) as store:
            store.transition(self.task, revision=0, target="applying",
                             approval_sha256="b" * 64, operation_id="op")
            store.recover()
        with patch.dict(os.environ, {"GH_TOKEN": ""}):
            with self.assertRaisesRegex(StateError, "GH_TOKEN required"):
                self.run_cli("recovery-github", "--id", self.task,
                             "--github-repo", "example/demo", "--branch", "agent/task-demo",
                             "--expected-commit", "d" * 40, "--base", "main",
                             "--title", "Fix", "--body", "Test")


if __name__ == "__main__":
    unittest.main()
