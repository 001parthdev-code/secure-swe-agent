"""A4 Linux-only: A3.2 approved E2 commit followed by trusted fixture verification."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from secure_swe_agent.verification import verify_calculator_fixture

TEST = """import unittest
from calculator import subtract
class CalculatorTest(unittest.TestCase):
    def test_subtract(self):
        self.assertEqual(subtract(8, 3), 5)
"""


def main():
    if sys.platform != 'linux' or len(sys.argv) != 2:
        raise SystemExit('usage: test_a4_linux_integration.py ENFORCER_CLI')
    cli = str(Path(sys.argv[1]).resolve(strict=True))
    repo = Path(__file__).resolve().parents[2]
    with tempfile.TemporaryDirectory(prefix='agent-a4-') as td:
        workspace = Path(td) / 'workspace'
        fixture = workspace / 'calculator'
        fixture.mkdir(parents=True)
        old = 'def subtract(a, b):\n    return a + b\n'
        new = 'def subtract(a, b):\n    return a - b\n'
        target = fixture / 'calculator.py'
        target.write_text(old)
        (fixture / 'test_calculator.py').write_text(TEST)
        before = verify_calculator_fixture(workspace)
        assert before['status'] == 'failed', before
        proposal = {'status': 'approval_required', 'applied': False, 'changes': [{
            'path': 'calculator/calculator.py',
            'base_sha256': hashlib.sha256(old.encode()).hexdigest(),
            'new_content': new,
            'diff': '-    return a + b\n+    return a - b\n'}]}
        proposal_path = Path(td) / 'proposal.json'
        raw = json.dumps(proposal).encode()
        proposal_path.write_bytes(raw)
        script = repo / 'agent' / 'apply_approved.py'
        args = [sys.executable, str(script), '--proposal', str(proposal_path),
                '--workspace', str(workspace), '--enforcer', cli]
        env = os.environ.copy()
        env.pop('ENFORCER_TRUSTED_EXCLUSIVE_WORKSPACE', None)
        review = subprocess.run(args, capture_output=True, text=True, env=env, check=True)
        approval = json.loads(review.stdout)['proposal_sha256']
        applied = subprocess.run(args + ['--approve-sha256', approval,
                                  '--trusted-exclusive-workspace'], capture_output=True,
                                 text=True, env=env)
        assert applied.returncode == 0, (applied.stdout, applied.stderr)
        after = verify_calculator_fixture(workspace)
        assert after['status'] == 'passed', after
        assert target.read_text() == new
        print('PASS: failing baseline -> approved E2 change -> passing unittest fixture')

if __name__ == '__main__':
    main()
