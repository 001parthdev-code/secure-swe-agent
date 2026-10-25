import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from secure_swe_agent.workflow import WorkflowError, apply, commit, review_commit

class A7Tests(unittest.TestCase):
    def test_invalid_proposal_fingerprint_never_starts_enforcer(self):
        with tempfile.TemporaryDirectory() as d:
            with patch('secure_swe_agent.workflow.EnforcerClient') as client:
                with self.assertRaises(FileNotFoundError):
                    apply(Path(d), Path(d)/'missing.json', 'bad', Path(d)/'enforcer')
                client.assert_not_called()

    def test_review_commit_rejects_other_files(self):
        with self.assertRaises(WorkflowError):
            review_commit(Path('.'), 'README.md')

    def test_commit_rejects_other_files(self):
        with self.assertRaises(WorkflowError):
            commit(Path('.'), 'README.md', '0'*64, 'test')

if __name__ == '__main__':
    unittest.main()
