"""LIVE-3 approval gates; all Git and network side effects mocked."""
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from fastapi.testclient import TestClient
from secure_swe_agent.live_api import LiveConfig, create_app


class Live3Tests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        (root/'workspace/calculator').mkdir(parents=True)
        (root/'workspace/calculator/calculator.py').write_text('bug')
        binary = root/'enforcer-cli'
        binary.write_text('stub')
        with patch.dict('os.environ', {'SWE_GITHUB_REPO':'example/demo', 'SWE_GITHUB_BASE':'main'}):
            self.client = TestClient(create_app(LiveConfig(root,binary,'x'*32,'http://127.0.0.1:5173')))
        self.headers = {'X-Operator-Token':'x'*32}
        self.path = '/api/tasks/task-1'
        # Initialize the task through the API then deterministically emulate the completed
        # LIVE-2 application. No actual model, Enforcer, Git, or network operations.
        import secure_swe_agent.live_api as live_api
        proposal = {'status':'approval_required','applied':False,'changes':[{'path':'calculator/calculator.py',
                    'new_content':'fixed','base_sha256':hashlib.sha256(b'bug').hexdigest()}]}
        class Result:
            returncode = 0
            stdout = json.dumps(proposal).encode()
        with patch.object(live_api.subprocess, 'run', return_value=Result()):
            response = self.client.post('/api/tasks',json={'description':'fix subtraction'},headers=self.headers)
            self.assertEqual(response.status_code,200)
            import time
            for _ in range(200):
                task = self.client.get('/api/tasks/current',headers=self.headers).json()
                if task['status'] != 'analyzing': break
                time.sleep(.005)
        self.assertEqual(task['status'],'awaiting_change_approval',task)
        self.id = task['id']
        from secure_swe_agent import workflow
        with patch.object(workflow,'prepare',return_value={}), patch.object(workflow,'apply',return_value={'status':'verified','verification':{'verified':True,'output':'Ran 6 tests in 0.1s'}}):
            self.client.post(f'/api/tasks/{self.id}/approve',headers=self.headers,json={'revision':task['revision'],'proposal_sha256':task['proposal_sha256']})
            for _ in range(200):
                task = self.client.get('/api/tasks/current',headers=self.headers).json()
                if task['status'] != 'applying': break
                time.sleep(.005)
        self.assertEqual(task['status'],'awaiting_commit_approval',task)

    def current(self):
        return self.client.get('/api/tasks/current',headers=self.headers).json()

    def test_commit_and_publish_review_approval(self):
        from secure_swe_agent import workflow
        with patch.object(workflow,'review_commit',return_value={'diff_untrusted':'diff','staged_sha256':'a'*64}), \
             patch.object(workflow,'commit',return_value={'status':'committed','commit':'b'*40}) as commit, \
             patch.object(workflow,'review_publish',return_value={'github_repo':'example/demo','branch':'agent/task-live','head':'b'*40,'base':'main','title':'Fix','body':'Test','approval_sha256':'c'*64}), \
             patch.object(workflow,'publish',return_value={'status':'pull_request_created','url':'https://github.com/example/demo/pull/1'}) as publish:
            url = f'/api/tasks/{self.id}'
            self.assertEqual(self.client.post(url+'/approve-commit',headers=self.headers,json={'revision':self.current()['revision'],'staged_sha256':'a'*64,'message':'Fix'}).status_code,409)
            self.assertEqual(self.client.post(url+'/review-commit',headers=self.headers).status_code,200)
            t=self.current()
            self.assertEqual(self.client.post(url+'/approve-commit',headers=self.headers,json={'revision':t['revision'],'staged_sha256':'0'*64,'message':'Fix'}).status_code,409)
            payload={'revision':t['revision'],'staged_sha256':'a'*64,'message':'Fix'}
            self.assertEqual(self.client.post(url+'/approve-commit',headers=self.headers,json=payload).status_code,200)
            self.assertEqual(self.client.post(url+'/approve-commit',headers=self.headers,json=payload).status_code,409)
            commit.assert_called_once()
            self.assertEqual(self.client.post(url+'/review-publish',headers=self.headers).status_code,200)
            t=self.current()
            self.assertEqual(self.client.post(url+'/approve-publish',headers=self.headers,json={'revision':t['revision'],'approval_sha256':'0'*64}).status_code,409)
            payload={'revision':t['revision'],'approval_sha256':'c'*64}
            result=self.client.post(url+'/approve-publish',headers=self.headers,json=payload)
            self.assertEqual(result.status_code,200,result.text)
            self.assertEqual(result.json()['status'],'published')
            self.assertEqual(self.client.post(url+'/approve-publish',headers=self.headers,json=payload).status_code,409)
            publish.assert_called_once()

    def test_unauthenticated_review_denied(self):
        self.assertEqual(self.client.post(f'/api/tasks/{self.id}/review-commit').status_code,401)

    def test_commit_failure_is_uncertain(self):
        from secure_swe_agent import workflow
        with patch.object(workflow,'review_commit',return_value={'diff_untrusted':'diff','staged_sha256':'a'*64}), \
             patch.object(workflow,'commit',side_effect=RuntimeError('unknown')):
            self.client.post(f'/api/tasks/{self.id}/review-commit',headers=self.headers)
            t=self.current()
            self.assertEqual(self.client.post(f'/api/tasks/{self.id}/approve-commit',headers=self.headers,json={'revision':t['revision'],'staged_sha256':'a'*64,'message':'Fix'}).status_code,409)
            self.assertEqual(self.current()['status'],'needs_reconciliation')

if __name__=='__main__': unittest.main()
