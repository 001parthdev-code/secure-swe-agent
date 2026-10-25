#!/usr/bin/env python3
"""Linux V0.1 integrated functional test; NOT a production isolation attestation."""
import json
import os
from pathlib import Path
import pwd
import subprocess
import sys
import tempfile


def check(condition, detail):
    if not condition:
        raise AssertionError(detail)


def main():
    if sys.platform != 'linux' or len(sys.argv) != 2:
        raise SystemExit('usage: verify-linux-v01-integrated.py /absolute/path/to/enforcer-cli')
    if os.geteuid() != 0:
        raise SystemExit('controlled E3 test requires root supervisor (sudo)')
    binary = str(Path(sys.argv[1]).resolve(strict=True))
    nobody = pwd.getpwnam('nobody')
    check(nobody.pw_uid != 0 and nobody.pw_gid != 0, 'untrusted identity must be non-root')
    with tempfile.TemporaryDirectory(prefix='enforcer-v01-') as tmp:
        root = Path(tmp)
        target = root / 'sample.txt'
        target.write_text('original', encoding='utf-8')
        env = os.environ.copy()
        env.update(ENFORCER_WORKSPACE=tmp,
                   ENFORCER_TRUSTED_EXCLUSIVE_WORKSPACE='1',
                   ENFORCER_ENABLE_FIXED_EXECUTION='1',
                   ENFORCER_EXEC_UID=str(nobody.pw_uid),
                   ENFORCER_EXEC_GID=str(nobody.pw_gid))
        # File-backed stderr prevents deadlock if audit output grows.
        with tempfile.TemporaryFile(mode='w+t', encoding='utf-8') as audit:
            proc = subprocess.Popen([binary], env=env, stdin=subprocess.PIPE,
                                    stdout=subprocess.PIPE, stderr=audit,
                                    text=True, encoding='utf-8', bufsize=1)
            actions = []
            def send(action, **fields):
                actions.append(action)
                proc.stdin.write(json.dumps({'action': action, **fields}) + '\n')
                proc.stdin.flush()
                line = proc.stdout.readline()
                check(bool(line), f'no response for {action}; process exit={proc.poll()}')
                return json.loads(line)
            try:
                read = send('read_file', path='sample.txt')
                check(read == {'status': 'success', 'output': 'original'}, f'read: {read}')
                created = send('create_file', path='new.txt', content='created')
                check(created['status'] == 'success' and (root / 'new.txt').read_text() == 'created', f'create: {created}')
                observed = send('get_file_version', path='sample.txt')
                check(observed['status'] == 'success' and observed['output'].startswith('ephemeral-v1:'), f'version: {observed}')
                token = observed['output']
                bad = send('modify_file_versioned', path='sample.txt', content='bad', expected_version='invalid')
                check(bad['status'] != 'success' and target.read_text() == 'original', f'invalid token: {bad}')
                good = send('modify_file_versioned', path='sample.txt', content='updated', expected_version=token)
                check(good['status'] == 'success' and target.read_text() == 'updated', f'modify: {good}')
                replay = send('modify_file_versioned', path='sample.txt', content='replay', expected_version=token)
                check(replay['status'] != 'success' and target.read_text() == 'updated', f'replay: {replay}')
                denied = send('run_command', command='/bin/sh')
                check(denied['status'] == 'policy_denied', f'command deny: {denied}')
                for name, code in [('true', 0), ('false', 1)]:
                    result = send('run_command', command=name)
                    check(result == {'status': 'success', 'output': f'exit_code={code}'}, f'{name}: {result}')
                invalid = send('read_file', path='../escape.txt')
                check(invalid['status'] != 'success', f'traversal: {invalid}')
            finally:
                proc.stdin.close()
                try:
                    proc.wait(timeout=8)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.wait(timeout=8)
            check(proc.returncode == 0, f'enforcer exited {proc.returncode}')
            audit.seek(0)
            lines = audit.read().splitlines()
            events = [json.loads(line) for line in lines if line.startswith('{')]
            check(len(events) == len(actions), f'audit count {len(events)} vs {len(actions)}; stderr={lines}')
            check([e['sequence'] for e in events] == list(range(1, len(actions) + 1)), 'audit sequence mismatch')
            check([e['action'] for e in events] == actions, 'audit action mismatch')
            check('ephemeral-v1:' not in '\n'.join(lines) and 'updated' not in '\n'.join(lines), 'sensitive content leaked to audit')
            print('PASS: Linux V0.1 integrated read/create/version/modify/replay/execute/deny/audit')
            print('LIMITATION: trusted-exclusive test workspace; fixed probes only; not a production sandbox')


if __name__ == '__main__':
    main()
