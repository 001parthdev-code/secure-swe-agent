import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from secure_swe_agent.proposals import propose_changes
from secure_swe_agent.approval import load_proposal
import json

class Enforcer:
    def read_file(self, path):
        return {'status': 'success', 'output': 'def subtract(a,b):\n    return a+b\n'}

class Model:
    def __init__(self, responses):
        self.responses = iter(responses)
        self.calls = 0
    def decide(self, messages):
        self.calls += 1
        return next(self.responses)

class Live1Tests(unittest.TestCase):
    def test_retry_empty_then_valid(self):
        model = Model([{'changes': []}, {'changes': [{'path': 'calculator/calculator.py', 'new_content': 'def subtract(a,b):\n    return a-b\n', 'rationale': 'correct arithmetic'}]}])
        result = propose_changes(model, Enforcer(), 'fix subtract', ['calculator/calculator.py'])
        self.assertEqual(model.calls, 2)
        self.assertEqual(result['status'], 'approval_required')
        load_proposal(json.dumps(result).encode())
    def test_persistent_empty_is_not_approval(self):
        result = propose_changes(Model([{'changes': []}, {'changes': []}]), Enforcer(), 'fix', ['calculator/calculator.py'])
        self.assertEqual(result['status'], 'no_change')
    def test_multiple_changes_rejected_after_bounded_retries(self):
        c = {'path': 'calculator/calculator.py', 'new_content': 'x', 'rationale': 'fix'}
        result = propose_changes(Model([{'changes': [c,c]}, {'changes': [c,c]}]), Enforcer(), 'fix', ['calculator/calculator.py'])
        self.assertEqual(result['status'], 'invalid_proposal')
    def test_invalid_attempt_limit(self):
        with self.assertRaises(ValueError):
            propose_changes(Model([]), Enforcer(), 'fix', ['calculator/calculator.py'], max_attempts=0)

if __name__ == '__main__':
    unittest.main()
