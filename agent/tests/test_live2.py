"""LIVE-2 API security tests; no real Enforcer or Git operations."""
import hashlib
import json
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from fastapi.testclient import TestClient
from secure_swe_agent.live_api import LiveConfig, create_app


class Live2Tests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        (root / 'workspace/calculator').mkdir(parents=True)
        self.source = root / 'workspace/calculator/calculator.py'
        self.source.write_text('def subtract(a,b): return a+b\n')
        exe = root / 'enforcer-cli'
        exe.write_text('stub')
        self.client = TestClient(create_app(LiveConfig(root, exe, 'a' * 32, 'http://127.0.0.1:5173')))
        self.auth = {'X-Operator-Token': 'a' * 32}
        self.proposal = {'status':'approval_required', 'applied':False,
                         'changes':[{'path':'calculator/calculator.py',
                         'new_content':'def subtract(a,b): return a-b\n',
                         'base_sha256':hashlib.sha256(self.source.read_bytes()).hexdigest()}]}
        self.raw = json.dumps(self.proposal).encode()

    def ready(self):
        from secure_swe_agent import live_api
        # Inject a deterministic successful analysis result, never real model calls.
        class Result:
            returncode = 0
            stdout = self.raw
        with patch.object(live_api.subprocess, 'run', return_value=Result()):
            r = self.client.post('/api/tasks', json={'description':'fix subtraction'}, headers=self.auth)
            self.assertEqual(r.status_code, 200)
            for _ in range(200):
                t = self.client.get('/api/tasks/current', headers=self.auth).json()
                if t['status'] != 'analyzing':
                    break
                time.sleep(.005)
        self.assertEqual(t['status'], 'awaiting_change_approval', t)
        return t

    def test_missing_auth_and_bad_fingerprint(self):
        t = self.ready()
        url = f"/api/tasks/{t['id']}/approve"
        self.assertEqual(self.client.post(url, json={'revision':t['revision'], 'proposal_sha256':t['proposal_sha256']}).status_code, 401)
        self.assertEqual(self.client.post(url, headers=self.auth, json={'revision':t['revision'], 'proposal_sha256':'0'*64}).status_code, 409)
        self.assertEqual(self.client.post(url, headers=self.auth, json={'revision':t['revision']-1, 'proposal_sha256':t['proposal_sha256']}).status_code, 409)

    def test_rejection_is_terminal(self):
        t = self.ready()
        url = f"/api/tasks/{t['id']}/reject"
        r = self.client.post(url, headers=self.auth, json={'revision':t['revision']})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()['status'], 'rejected')
        self.assertEqual(self.client.post(url, headers=self.auth, json={'revision':t['revision']}).status_code, 409)

    def test_approved_apply_and_duplicate_denial(self):
        t = self.ready()
        from secure_swe_agent import workflow
        with patch.object(workflow, 'prepare', return_value={'status':'awaiting_apply_approval'}), \
             patch.object(workflow, 'apply', return_value={'status':'verified', 'verification':{'verified':True,'output':'Ran 6 tests\\nOK'}}):
            url = f"/api/tasks/{t['id']}/approve"
            payload = {'revision':t['revision'], 'proposal_sha256':t['proposal_sha256']}
            r = self.client.post(url, headers=self.auth, json=payload)
            self.assertEqual(r.status_code, 200)
            self.assertEqual(self.client.post(url, headers=self.auth, json=payload).status_code, 409)
            for _ in range(200):
                now = self.client.get('/api/tasks/current', headers=self.auth).json()
                if now['status'] != 'applying': break
                time.sleep(.005)
            self.assertEqual(now['status'], 'awaiting_commit_approval', now)
            self.assertEqual(now['tests']['failed'], 0)

if __name__ == '__main__': unittest.main()
