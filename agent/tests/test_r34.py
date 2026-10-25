"""R3.4 journal-first and immutable-artifact regression checks."""
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from secure_swe_agent.durable_a7 import DurableA7
from secure_swe_agent.workflow_state import StateError, WorkflowStore


class RecoveryHardeningTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.repo = self.root / 'repo'
        self.repo.mkdir()
        self.db = self.root / 'journal.sqlite'
        self.store = WorkflowStore(self.db)
        self.addCleanup(self.store.close)
        self.adapter = DurableA7(self.store)
        self.raw = json.dumps({'status':'approval_required','applied':False,'changes':[
            {'path':'calculator/calculator.py','new_content':'fixed', 'base_sha256':'a'*64}]}).encode()
        self.proposal = self.root / 'proposal.json'
        self.proposal.write_bytes(self.raw)

    def test_prepare_journals_before_branch_side_effect(self):
        def check(*args):
            rows = self.store.db.execute('SELECT state FROM workflows').fetchall()
            self.assertEqual([r['state'] for r in rows], ['preparing'])
            raise OSError('branch creation interrupted')
        with patch('secure_swe_agent.durable_a7.workflow.prepare', side_effect=check):
            with self.assertRaises(OSError):
                self.adapter.prepare(self.repo, self.proposal, 'fix')
        row = self.store.db.execute('SELECT id,state FROM workflows').fetchone()
        self.assertEqual(row['state'], 'needs_reconciliation')
        self.assertEqual(self.store.events(row['id'])[-1]['kind'], 'prepare_uncertain')

    def test_prepare_stores_exact_proposal_and_restarts(self):
        with patch('secure_swe_agent.durable_a7.workflow.prepare', return_value={
            'status':'awaiting_apply_approval','proposal_sha256':hashlib.sha256(self.raw).hexdigest()}):
            result = self.adapter.prepare(self.repo, self.proposal, 'fix')
        task = result['workflow_id']
        self.assertEqual(result['revision'], 1)
        self.assertEqual(self.adapter.proposal_path(task).read_bytes(), self.raw)
        self.proposal.write_text('tampered')
        with self.assertRaisesRegex(StateError, 'differs'):
            self.adapter.apply(task, 1, self.repo, self.proposal,
                               hashlib.sha256(self.raw).hexdigest(), self.root/'enforcer')
        self.assertEqual(self.store.get(task)['state'], 'awaiting_apply_approval')
        self.adapter.proposal_path(task).write_text('tampered')
        with self.assertRaisesRegex(StateError, 'changed'):
            self.adapter.proposal_path(task)

    def test_recover_preparing_does_not_replay(self):
        row = self.store.create(self.repo, 'a'*64, preparing=True)
        self.store.close()
        with WorkflowStore(self.db) as reopened:
            affected = reopened.recover()
            self.assertEqual(affected[0]['state'], 'needs_reconciliation')
            self.assertEqual(reopened.get(row['id'])['revision'], 1)
            self.assertEqual(reopened.recover(), [])


if __name__ == '__main__':
    unittest.main()
