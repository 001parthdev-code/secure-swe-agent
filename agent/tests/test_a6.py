import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from secure_swe_agent.git_broker import GitBrokerError
from secure_swe_agent.github_broker import preview_publish, publish_approved


def git(repo, *args):
    return subprocess.run(["git", "-C", str(repo), *args], check=True,
                          capture_output=True, text=True).stdout.strip()


class PublishTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.repo = Path(self.temp.name)
        git(self.repo, "init", "-b", "main")
        git(self.repo, "config", "user.name", "Tester")
        git(self.repo, "config", "user.email", "test@example.invalid")
        (self.repo / "code.py").write_text("x = 1\n")
        git(self.repo, "add", "code.py")
        git(self.repo, "commit", "-m", "initial")
        git(self.repo, "switch", "-c", "agent/task-demo")
        git(self.repo, "remote", "add", "origin", "https://github.com/example/demo.git")

    def test_preview_no_network(self):
        result = preview_publish(self.repo, "example/demo", "main", title="Fix", body="Test")
        self.assertEqual(result["status"], "approval_required")
        self.assertEqual(len(result["approval_sha256"]), 64)

    def test_configured_https_origin_survives_git_ssh_rewrite(self):
        git(self.repo, "config", "url.git@github.com:.insteadOf", "https://github.com/")
        self.assertTrue(git(self.repo, "remote", "get-url", "origin").startswith("git@github.com:"))
        result = preview_publish(self.repo, "example/demo", "main", title="Fix", body="Test")
        self.assertEqual(result["status"], "approval_required")

    def test_remote_with_embedded_credentials_rejected(self):
        git(self.repo, "remote", "set-url", "origin", "https://user:secret@github.com/example/demo.git")
        with self.assertRaisesRegex(GitBrokerError, "credential-free"):
            preview_publish(self.repo, "example/demo", "main", title="Fix", body="Test")

    def test_wrong_origin_rejected(self):
        with self.assertRaises(GitBrokerError):
            preview_publish(self.repo, "someone/else", "main", title="Fix", body="Test")

    def test_dirty_repo_rejected(self):
        (self.repo / "code.py").write_text("x = 2\n")
        with self.assertRaises(GitBrokerError):
            preview_publish(self.repo, "example/demo", "main", title="Fix", body="Test")

    def test_commit_change_invalidates_approval(self):
        approved = preview_publish(self.repo, "example/demo", "main", title="Fix", body="Test")
        (self.repo / "code.py").write_text("x = 2\n")
        git(self.repo, "add", "code.py")
        git(self.repo, "commit", "-m", "change")
        with patch.dict(os.environ, {"GH_TOKEN": "dummy"}):
            with self.assertRaisesRegex(GitBrokerError, "changed since approval"):
                publish_approved(self.repo, "example/demo", approved["approval_sha256"],
                                 base="main", title="Fix", body="Test")

    def test_missing_token_blocks_network(self):
        approved = preview_publish(self.repo, "example/demo", "main", title="Fix", body="Test")
        with patch.dict(os.environ, {"GH_TOKEN": ""}):
            with self.assertRaisesRegex(GitBrokerError, "GH_TOKEN required"):
                publish_approved(self.repo, "example/demo", approved["approval_sha256"],
                                 base="main", title="Fix", body="Test")


if __name__ == "__main__":
    unittest.main()
