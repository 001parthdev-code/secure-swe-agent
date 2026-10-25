import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from secure_swe_agent.proposals import propose_changes

class Model:
    def __init__(self, response): self.response = response
    def decide(self, messages): return self.response

class Enforcer:
    def __init__(self): self.calls = []
    def read_file(self, path):
        self.calls.append(path)
        return {'status':'success','output':'before\n'}

class ProposalTests(unittest.TestCase):
    def test_produces_reviewable_diff_without_write(self):
        e = Enforcer()
        result = propose_changes(Model({'changes':[{'path':'main.py','new_content':'after\n','rationale':'fix'}]}), e, 'fix', ['main.py'])
        self.assertEqual(result['status'], 'approval_required')
        self.assertFalse(result['applied'])
        self.assertIn('-before', result['changes'][0]['diff'])
        self.assertEqual(e.calls, ['main.py'])
    def test_rejects_unapproved_path(self):
        e = Enforcer()
        result = propose_changes(Model({'changes':[{'path':'../secret','new_content':'oops','rationale':'x'}]}), e, 'x', ['main.py'])
        self.assertEqual(result['status'], 'invalid_proposal')
    def test_rejects_duplicate_changes(self):
        c = {'path':'main.py','new_content':'after','rationale':'x'}
        self.assertEqual(propose_changes(Model({'changes':[c,c]}), Enforcer(), 'x', ['main.py'])['status'], 'invalid_proposal')
    def test_rejects_invalid_catalog(self):
        with self.assertRaises(ValueError): propose_changes(Model({}), Enforcer(), 'x', ['../secret'])
    def test_empty_changes(self):
        self.assertEqual(propose_changes(Model({'changes':[]}), Enforcer(), 'x', ['main.py'])['changes'], [])

if __name__ == '__main__': unittest.main()
