"""Offline publishing recovery tests. Never contact GitHub."""
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from secure_swe_agent import github_broker as broker
from secure_swe_agent.git_broker import GitBrokerError


def git(repo, *args):
    return subprocess.run(["git", "-C", str(repo), *args], check=True,
                          capture_output=True, text=True).stdout.strip()


class RecoveryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.repo = Path(self.temp.name)
        git(self.repo, "init", "-b", "main")
        git(self.repo, "config", "user.name", "Tester")
        git(self.repo, "config", "user.email", "test@example.invalid")
        (self.repo / "code.py").write_text("x=1\n")
        git(self.repo, "add", "code.py")
        git(self.repo, "commit", "-m", "init")
        git(self.repo, "switch", "-c", "agent/task-demo")
        git(self.repo, "remote", "add", "origin", "https://github.com/example/demo.git")
        self.plan = broker.preview_publish(self.repo, "example/demo", "main", title="Fix", body="Test")
        self.head = self.plan["head"]
        self.pr = {"head": {"sha": self.head, "ref": "agent/task-demo"},
                   "base": {"ref": "main"}, "title": "Fix", "body": "Test",
                   "html_url": "https://github.com/example/demo/pull/1"}

    def publish(self):
        with patch.dict(os.environ, {"GH_TOKEN": "dummy"}):
            return broker.publish_approved(self.repo, "example/demo",
                                           self.plan["approval_sha256"],
                                           base="main", title="Fix", body="Test")

    def test_existing_matching_pr_is_idempotent(self):
        with patch.object(broker, "_remote_head", return_value=self.head), \
             patch.object(broker, "_github_request", return_value=[self.pr]) as request, \
             patch.object(broker, "_push_guard") as push:
            result = self.publish()
        self.assertEqual(result["status"], "pull_request_exists")
        push.assert_not_called()
        self.assertEqual(request.call_count, 1)

    def test_differing_remote_commit_blocks_push(self):
        with patch.object(broker, "_remote_head", return_value="a" * 40), \
             patch.object(broker, "_github_request") as api, \
             patch.object(broker, "_push_guard") as push:
            with self.assertRaisesRegex(GitBrokerError, "remote branch differs"):
                self.publish()
        api.assert_not_called()
        push.assert_not_called()

    def test_recover_pushed_branch_and_create_pr(self):
        with patch.object(broker, "_remote_head", return_value=self.head), \
             patch.object(broker, "_github_request", side_effect=[[], {"html_url": self.pr["html_url"]}]) as api, \
             patch.object(broker, "_push_guard") as push:
            result = self.publish()
        self.assertEqual(result["status"], "pull_request_created")
        self.assertEqual(api.call_count, 2)
        push.assert_not_called()

    def test_conflicting_existing_pr_blocks_publish(self):
        conflicting = dict(self.pr, title="Different title")
        with patch.object(broker, "_remote_head", return_value=self.head), \
             patch.object(broker, "_github_request", return_value=[conflicting]), \
             patch.object(broker, "_push_guard") as push:
            with self.assertRaisesRegex(GitBrokerError, "existing PR does not match"):
                self.publish()
        push.assert_not_called()

    def test_unknown_remote_ref_refuses_pr(self):
        with patch.object(broker, "_remote_head", side_effect=[None, None]), \
             patch.object(broker, "_github_request", return_value=[]) as api, \
             patch.object(broker, "_push_guard") as push:
            push.return_value.returncode = 0
            with self.assertRaisesRegex(GitBrokerError, "does not match approved commit"):
                self.publish()
        api.assert_called_once()


if __name__ == "__main__":
    unittest.main()
