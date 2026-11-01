import subprocess
import sys
import tempfile
import os
from unittest.mock import patch
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

    def test_git_child_does_not_inherit_operator_tokens(self):
        from secure_swe_agent.git_broker import _git
        original_run = subprocess.run
        seen = []

        def checked_run(*args, **kwargs):
            seen.append(kwargs.get("env"))
            return original_run(*args, **kwargs)

        with patch.dict(os.environ, {"GH_TOKEN": "private-gh", "GITHUB_TOKEN": "private-github", "SWE_API_TOKEN": "private-api"}):
            with patch("secure_swe_agent.git_broker.subprocess.run", side_effect=checked_run):
                self.assertEqual(_git(self.repo, "rev-parse", "--is-bare-repository").strip(), "false")
        self.assertEqual(len(seen), 1)
        for secret in ("GH_TOKEN", "GITHUB_TOKEN", "SWE_API_TOKEN"):
            self.assertNotIn(secret, seen[0])

    def test_approved_local_commit(self):
        self.assertEqual(create_task_branch(self.repo, "fix-1"), "agent/task-fix-1")
        (self.repo / "code.py").write_text("value = 2\n")
        preview = prepare_commit(self.repo, "code.py")
        with self.assertRaises(GitBrokerError):
            commit_approved(self.repo, "code.py", "0" * 64, "Fix value")
        result = commit_approved(self.repo, "code.py", preview["staged_sha256"], "Fix value")
        self.assertEqual(result["status"], "committed")
        self.assertEqual(result["branch"], "agent/task-fix-1")

    def test_approval_not_replayable_on_other_branch(self):
        create_task_branch(self.repo, "first")
        (self.repo / "code.py").write_text("value = 2\n")
        approval = prepare_commit(self.repo, "code.py")["staged_sha256"]
        git(self.repo, "reset", "--hard", "HEAD")
        git(self.repo, "switch", "main")
        create_task_branch(self.repo, "second")
        (self.repo / "code.py").write_text("value = 2\n")
        prepare_commit(self.repo, "code.py")
        with self.assertRaisesRegex(GitBrokerError, "changed since approval"):
            commit_approved(self.repo, "code.py", approval, "Fix value")

    def test_approval_not_replayable_in_different_repository(self):
        create_task_branch(self.repo, "first")
        (self.repo / "code.py").write_text("value = 2\n")
        approved = prepare_commit(self.repo, "code.py")["staged_sha256"]
        with tempfile.TemporaryDirectory() as other_dir:
            other = Path(other_dir)
            git(other, "init", "-b", "main")
            git(other, "config", "user.name", "Test Operator")
            git(other, "config", "user.email", "operator@example.invalid")
            (other / "code.py").write_text("value = 1\n")
            git(other, "add", "code.py")
            git(other, "commit", "-m", "initial")
            create_task_branch(other, "first")
            (other / "code.py").write_text("value = 2\n")
            prepare_commit(other, "code.py")
            with self.assertRaisesRegex(GitBrokerError, "changed since approval"):
                commit_approved(other, "code.py", approved, "Fix value")

    def test_approval_invalidated_by_head_change(self):
        create_task_branch(self.repo, "head-change")
        (self.repo / "code.py").write_text("value = 2\n")
        approval = prepare_commit(self.repo, "code.py")["staged_sha256"]
        # Change HEAD while preserving the staged diff.
        tree = subprocess.run(["git", "-C", str(self.repo), "rev-parse", "HEAD^{tree}"],
                              check=True, capture_output=True, text=True).stdout.strip()
        parent = subprocess.run(["git", "-C", str(self.repo), "rev-parse", "HEAD"],
                                check=True, capture_output=True, text=True).stdout.strip()
        new_head = subprocess.run(["git", "-C", str(self.repo), "commit-tree", tree,
                                   "-p", parent, "-m", "unrelated commit"],
                                  check=True, capture_output=True, text=True).stdout.strip()
        git(self.repo, "update-ref", "HEAD", new_head)
        with self.assertRaisesRegex(GitBrokerError, "changed since approval"):
            commit_approved(self.repo, "code.py", approval, "Fix value")

    def test_repeated_review_is_idempotent(self):
        create_task_branch(self.repo, "repeat")
        (self.repo / "code.py").write_text("value = 2\n")
        first = prepare_commit(self.repo, "code.py")
        second = prepare_commit(self.repo, "code.py")
        self.assertEqual(first["staged_sha256"], second["staged_sha256"])
        self.assertEqual(first["diff_untrusted"], second["diff_untrusted"])

    def test_repeated_review_rejects_unstaged_changes(self):
        create_task_branch(self.repo, "repeat")
        (self.repo / "code.py").write_text("value = 2\n")
        prepare_commit(self.repo, "code.py")
        (self.repo / "code.py").write_text("value = 3\n")
        with self.assertRaisesRegex(GitBrokerError, "unstaged changes"):
            prepare_commit(self.repo, "code.py")

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
