import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from secure_swe_agent.workflow_state import StateError, WorkflowStore


class WorkflowStateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.db = self.root / 'state.sqlite3'
        self.store = WorkflowStore(self.db)
        self.addCleanup(self.store.close)
        self.task = self.store.create(self.root, 'a' * 64)

    def test_persists_after_reopen(self):
        with WorkflowStore(self.db) as reopened:
            self.assertEqual(reopened.get(self.task['id'])['state'], 'awaiting_apply_approval')
            self.assertEqual(len(reopened.events(self.task['id'])), 1)

    def test_stale_revision_and_invalid_transition(self):
        with self.assertRaisesRegex(StateError, 'invalid workflow transition'):
            self.store.transition(self.task['id'], revision=0, target='published')
        self.store.transition(self.task['id'], revision=0, target='cancelled')
        with self.assertRaisesRegex(StateError, 'stale workflow revision'):
            self.store.transition(self.task['id'], revision=0, target='cancelled')
        self.assertEqual(len(self.store.events(self.task['id'])), 2)

    def test_approval_and_operation_required(self):
        with self.assertRaisesRegex(StateError, 'operation ID'):
            self.store.transition(self.task['id'], revision=0, target='applying', approval_sha256='b'*64)
        with self.assertRaisesRegex(StateError, 'approval digest'):
            self.store.transition(self.task['id'], revision=0, target='applying', operation_id='apply-1')

    def test_restart_requires_reconciliation(self):
        self.store.transition(self.task['id'], revision=0, target='applying',
                              approval_sha256='b'*64, operation_id='apply-1')
        with WorkflowStore(self.db) as restarted:
            changed = restarted.recover()
            self.assertEqual(len(changed), 1)
            self.assertEqual(changed[0]['state'], 'needs_reconciliation')
            self.assertEqual(restarted.recover(), [])
            with self.assertRaisesRegex(StateError, 'stale workflow revision'):
                restarted.transition(self.task['id'], revision=1, target='awaiting_commit_approval')
            self.assertEqual(len(restarted.events(self.task['id'])), 3)

    def test_multiple_connections_cas(self):
        with WorkflowStore(self.db) as second:
            self.store.transition(self.task['id'], revision=0, target='cancelled')
            with self.assertRaisesRegex(StateError, 'stale workflow revision'):
                second.transition(self.task['id'], revision=0, target='cancelled')


if __name__ == '__main__':
    unittest.main()
