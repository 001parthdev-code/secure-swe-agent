"""Run only via Linux CI with an existing built Enforcer CLI."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile


def main():
    if sys.platform != 'linux' or len(sys.argv) != 2:
        raise SystemExit('usage (Linux): test_a32_linux_integration.py ENFORCER_EXECUTABLE')
    cli = str(Path(sys.argv[1]).resolve(strict=True))
    repo = Path(__file__).resolve().parents[2]
    with tempfile.TemporaryDirectory(prefix='agent-a32-') as td:
        workspace = Path(td) / 'workspace'
        workspace.mkdir()
        (workspace / 'calculator').mkdir()
        target = workspace / 'calculator' / 'calculator.py'
        old = 'def subtract(a, b):\n    return a + b\n'
        new = 'def subtract(a, b):\n    return a - b\n'
        target.write_text(old)
        proposal = {'status': 'approval_required', 'applied': False, 'changes': [
            {'path': 'calculator/calculator.py',
             'base_sha256': hashlib.sha256(old.encode()).hexdigest(),
             'new_content': new,
             'diff': '-    return a + b\n+    return a - b\n'}]}
        artifact = Path(td) / 'proposal.json'
        artifact.write_text(json.dumps(proposal))
        script = repo / 'agent' / 'apply_approved.py'
        cmd = [sys.executable, str(script), '--proposal', str(artifact),
               '--workspace', str(workspace), '--enforcer', cli]
        env = os.environ.copy()
        env.pop('ENFORCER_TRUSTED_EXCLUSIVE_WORKSPACE', None)
        inspect = subprocess.run(cmd, capture_output=True, text=True, env=env, check=True)
        hash_value = json.loads(inspect.stdout)['proposal_sha256']
        denied = subprocess.run(cmd + ['--approve-sha256', hash_value], capture_output=True, text=True, env=env)
        assert denied.returncode != 0 and target.read_text() == old, 'unapproved mutation occurred'
        approved = subprocess.run(cmd + ['--approve-sha256', hash_value,
                                         '--trusted-exclusive-workspace'], capture_output=True, text=True, env=env)
        assert approved.returncode == 0, f'approved application failed: {approved.stdout} {approved.stderr}'
        assert target.read_text() == new, 'approved replacement not committed'
        print('PASS: explicit approval gate, E2 versioned commit, and content verification')


if __name__ == '__main__':
    main()
