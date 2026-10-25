"""R3.4.3 operator-gated recovery and read-only remote evidence."""
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from secure_swe_agent.workflow_state import WorkflowStore, StateError
from secure_swe_agent.recovery_evidence import github_evidence


class RecoveryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        self.repo = root / 'repo'
        self.repo.mkdir()
        self.store = WorkflowStore(root / 'state.db')
        self.addCleanup(self.store.close)
        self.id = self.store.create(self.repo, 'a' * 64)['id']
        self.store.transition(self.id, revision=0, target='applying',
                              approval_sha256='b' * 64, operation_id='op')
        self.fence = self.store.acquire_operation(self.id, 'old', ttl=1)

    def test_expired_owner_not_sufficient(self):
        self.store.db.execute('UPDATE operation_owners SET expires_at=0')
        with self.assertRaisesRegex(StateError, 'termination confirmation'):
            self.store.quarantine_abandoned_owner(self.id, owner='old', fence=self.fence,
                                                  confirmed_stopped=False)
        self.assertIsNotNone(self.store.operation_owner(self.id))

    def test_wrong_fence_cannot_quarantine(self):
        with self.assertRaisesRegex(StateError, 'ownership mismatch'):
            self.store.quarantine_abandoned_owner(self.id, owner='old', fence=self.fence+1,
                                                  confirmed_stopped=True)
        self.assertEqual(self.store.get(self.id)['state'], 'applying')

    def test_operator_quarantine_is_atomic_and_non_replaying(self):
        with WorkflowStore(self.store.path) as restarted:
            row = restarted.quarantine_abandoned_owner(self.id, owner='old', fence=self.fence,
                                                       confirmed_stopped=True)
            self.assertEqual(row['state'], 'needs_reconciliation')
            self.assertIsNone(restarted.operation_owner(self.id))
            self.assertEqual(restarted.events(self.id)[-1]['kind'], 'owner_quarantined')
            with self.assertRaisesRegex(StateError, 'reconciliation'):
                restarted.acquire_operation(self.id, 'new')
            with self.assertRaises(StateError):
                restarted.quarantine_abandoned_owner(self.id, owner='old', fence=self.fence,
                                                     confirmed_stopped=True)

    def test_remote_evidence_does_not_mutate_state(self):
        self.store.quarantine_abandoned_owner(self.id, owner='old', fence=self.fence,
                                              confirmed_stopped=True)
        kwargs = dict(github_repo='example/demo', branch='agent/task-demo',
                      expected_commit='c'*40, base='main', title='Fix', body='Body', token='fake')
        with patch('secure_swe_agent.github_broker._origin', return_value='https://github.com/example/demo.git'), \
             patch('secure_swe_agent.github_broker._remote_head', return_value='c'*40), \
             patch('secure_swe_agent.github_broker._existing_pr', return_value={
                 'url':'https://github.com/example/demo/pull/1'}):
            evidence = github_evidence(self.store, self.id, **kwargs)
        self.assertEqual(evidence['outcome'], 'matching_pr')
        self.assertTrue(evidence['matches'])
        self.assertEqual(self.store.get(self.id)['state'], 'needs_reconciliation')

    def test_conflicting_remote_commit_skips_pr_lookup(self):
        self.store.quarantine_abandoned_owner(self.id, owner='old', fence=self.fence,
                                              confirmed_stopped=True)
        with patch('secure_swe_agent.github_broker._origin'), \
             patch('secure_swe_agent.github_broker._remote_head', return_value='d'*40), \
             patch('secure_swe_agent.github_broker._existing_pr') as pr:
            evidence = github_evidence(self.store, self.id, github_repo='example/demo',
                                      branch='agent/task-demo', expected_commit='c'*40,
                                      base='main', title='Fix', body='Body', token='fake')
        self.assertEqual(evidence['outcome'], 'branch_conflict')
        pr.assert_not_called()

if __name__ == '__main__':
    unittest.main()
