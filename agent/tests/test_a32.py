import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import json
import unittest
from secure_swe_agent.approval import ApprovalError, apply_approved, digest, load_proposal


class FakeEnforcer:
    def __init__(self, text='before'):
        self.text = text
        self.calls = []

    def read_file(self, path):
        return {'status': 'success', 'output': self.text}

    def get_file_version(self, path):
        return {'status': 'success', 'output': 'ephemeral-v1:test'}

    def modify_file_versioned(self, path, content, token):
        self.calls.append((path, content, token))
        self.text = content
        return {'status': 'success', 'output': 'ok'}


def proposal():
    return {'status': 'approval_required', 'applied': False, 'changes': [
        {'path': 'calculator/calculator.py', 'base_sha256': digest(b'before'),
         'new_content': 'after', 'diff': '-before\n+after\n'}]}


class ApprovalTests(unittest.TestCase):
    def test_approved_applies_through_enforcer(self):
        p = load_proposal(json.dumps(proposal()).encode())
        e = FakeEnforcer()
        self.assertEqual(apply_approved(p, e, {'calculator/calculator.py'})['status'], 'applied')
        self.assertEqual(e.text, 'after')
        self.assertEqual(len(e.calls), 1)

    def test_stale_fails_without_write(self):
        e = FakeEnforcer('changed')
        result = apply_approved(proposal(), e, {'calculator/calculator.py'})
        self.assertEqual(result['status'], 'stale_proposal')
        self.assertEqual(e.calls, [])

    def test_unapproved_path_rejected(self):
        with self.assertRaises(ApprovalError):
            apply_approved(proposal(), FakeEnforcer(), {'other.py'})

    def test_invalid_paths_rejected(self):
        p = proposal()
        p['changes'][0]['path'] = '../secret'
        with self.assertRaises(ApprovalError):
            load_proposal(json.dumps(p).encode())

    def test_proposal_hash_changes_on_edit(self):
        a = json.dumps(proposal()).encode()
        b = a.replace(b'after', b'evil')
        self.assertNotEqual(digest(a), digest(b))


if __name__ == '__main__':
    unittest.main()
