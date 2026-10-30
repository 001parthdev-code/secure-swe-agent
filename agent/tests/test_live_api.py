"""Local API boundary tests; no Ollama, Enforcer, Git or network invoked."""
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from fastapi.testclient import TestClient
from secure_swe_agent.live_api import LiveConfig, create_app


class LiveApiTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        (root / 'workspace/calculator').mkdir(parents=True)
        (root / 'workspace/calculator/calculator.py').write_text('def subtract(a,b): return a+b\n')
        exe = root / 'enforcer-cli'
        exe.write_text('placeholder')
        self.app = create_app(LiveConfig(root, exe, 'x' * 32, 'http://127.0.0.1:5173'))
        self.client = TestClient(self.app)
        self.headers = {'X-Operator-Token': 'x' * 32}

    def test_authentication_required(self):
        self.assertEqual(self.client.get('/api/tasks/current').status_code, 401)
        self.assertEqual(self.client.get('/api/health', headers=self.headers).status_code, 200)

    def test_scope_and_no_writes(self):
        self.assertEqual(self.client.post('/api/tasks', headers=self.headers,
                                        json={'description':'Modify arbitrary files'}).status_code, 422)
        self.assertEqual(self.client.post('/api/tasks/anything/approve', headers=self.headers).status_code, 409)

    def test_no_task(self):
        self.assertEqual(self.client.get('/api/tasks/current', headers=self.headers).json(), {'status':'no_task'})

    def test_invalid_origin(self):
        with self.assertRaises(ValueError):
            LiveConfig(Path(self.tmp.name), Path(self.tmp.name) / 'enforcer-cli',
                       'x' * 32, 'https://public.example')

if __name__ == '__main__':
    unittest.main()
