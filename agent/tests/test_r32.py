import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from secure_swe_agent.durable_a7 import DurableA7
from secure_swe_agent.workflow_state import WorkflowStore, StateError

class DurableA7Tests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.repo = Path(self.tmp.name)
        self.store = WorkflowStore(self.repo / 'state.sqlite')
        self.addCleanup(self.store.close)
        self.adapter = DurableA7(self.store)
        self.approval = 'a' * 64
        self.row = self.store.create(self.repo, self.approval)

    def test_successful_apply_is_durable(self):
        with patch('secure_swe_agent.durable_a7.workflow.apply', return_value={'status':'verified'}):
            result = self.adapter.apply(self.row['id'], 0, self.repo, self.repo/'proposal.json', self.approval, self.repo/'enforcer')
        self.assertEqual(result['state'], 'awaiting_commit_approval')
        self.assertEqual(self.store.get(self.row['id'])['revision'], 2)

    def test_stale_revision_prevents_side_effect(self):
        with patch('secure_swe_agent.durable_a7.workflow.apply') as operation:
            with self.assertRaises(StateError):
                self.adapter.apply(self.row['id'], 9, self.repo, self.repo/'proposal.json', self.approval, self.repo/'enforcer')
            operation.assert_not_called()

    def test_exception_requires_reconciliation(self):
        with patch('secure_swe_agent.durable_a7.workflow.apply', side_effect=OSError('interrupted')):
            with self.assertRaises(OSError):
                self.adapter.apply(self.row['id'], 0, self.repo, self.repo/'proposal.json', self.approval, self.repo/'enforcer')
        self.assertEqual(self.store.get(self.row['id'])['state'], 'needs_reconciliation')

    def test_restart_marks_inflight_uncertain(self):
        self.store.transition(self.row['id'], revision=0, target='applying', approval_sha256=self.approval, operation_id='operation1')
        self.store.recover()
        self.assertEqual(self.store.get(self.row['id'])['state'], 'needs_reconciliation')

if __name__ == '__main__': unittest.main()
