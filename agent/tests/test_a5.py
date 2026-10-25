import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from secure_swe_agent.git_broker import (
    GitBrokerError, create_task_branch, prepare_commit, commit_approved,
)


def git(repo, *args):
    subprocess.run(["git", "-C", str(repo), *args], check=True,
                   capture_output=True)


class GitBrokerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.repo = Path(self.tmp.name)
        git(self.repo, "init", "-b", "main")
        git(self.repo, "config", "user.name", "Test Operator")
        git(self.repo, "config", "user.email", "operator@example.invalid")
        (self.repo / "code.py").write_text("value = 1\n")
        git(self.repo, "add", "code.py")
        git(self.repo, "commit", "-m", "initial")

    def test_approved_local_commit(self):
        self.assertEqual(create_task_branch(self.repo, "fix-1"), "agent/task-fix-1")
        (self.repo / "code.py").write_text("value = 2\n")
        preview = prepare_commit(self.repo, "code.py")
        with self.assertRaises(GitBrokerError):
            commit_approved(self.repo, "code.py", "0" * 64, "Fix value")
        result = commit_approved(self.repo, "code.py", preview["staged_sha256"], "Fix value")
        self.assertEqual(result["status"], "committed")
        self.assertEqual(result["branch"], "agent/task-fix-1")

    def test_no_direct_main_commit(self):
        (self.repo / "code.py").write_text("value = 2\n")
        with self.assertRaises(GitBrokerError):
            prepare_commit(self.repo, "code.py")

    def test_dirty_branch_denied(self):
        (self.repo / "code.py").write_text("value = 2\n")
        with self.assertRaises(GitBrokerError):
            create_task_branch(self.repo, "dirty")

    def test_untracked_file_denied(self):
        create_task_branch(self.repo, "safe")
        (self.repo / "untracked.py").write_text("hi")
        with self.assertRaises(GitBrokerError):
            prepare_commit(self.repo, "untracked.py")

    def test_diff_changed_denied(self):
        create_task_branch(self.repo, "safe")
        (self.repo / "code.py").write_text("value = 2\n")
        preview = prepare_commit(self.repo, "code.py")
        (self.repo / "code.py").write_text("value = 3\n")
        with self.assertRaises(GitBrokerError):
            commit_approved(self.repo, "code.py", preview["staged_sha256"], "Fix value")


if __name__ == "__main__":
    unittest.main()
