#!/usr/bin/env python3
"""Linux-only, disposable E2 JSON protocol integration test.

This is a trusted-exclusive prototype test, not an isolation attestation.
"""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def request(proc, action, **kwargs):
    payload = json.dumps({'action': action, **kwargs}, separators=(',', ':'))
    proc.stdin.write(payload + '\n')
    proc.stdin.flush()
    line = proc.stdout.readline()
    require(line != '', f'enforcer exited or produced no response for {action}')
    return json.loads(line)


def status(result):
    return result.get('status')


def main():
    if sys.platform != 'linux':
        raise SystemExit('Linux-only integration test')
    if len(sys.argv) != 2:
        raise SystemExit('usage: verify-linux-e2-versioned.py PATH_TO_ENFORCER_CLI')
    executable = str(Path(sys.argv[1]).resolve())
    with tempfile.TemporaryDirectory(prefix='enforcer-e2-') as tmp:
        workspace = Path(tmp)
        target = workspace / 'sample.txt'
        target.write_text('original', encoding='utf-8')
        env = os.environ.copy()
        env['ENFORCER_WORKSPACE'] = str(workspace)
        env['ENFORCER_TRUSTED_EXCLUSIVE_WORKSPACE'] = '1'
        with subprocess.Popen([executable], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE, text=True, encoding='utf-8',
                              bufsize=1, env=env) as proc:
            try:
                observed = request(proc, 'get_file_version', path='sample.txt')
                require(status(observed) == 'success', f'version observation: {observed}')
                token = observed['output']
                require(token.startswith('ephemeral-v1:'), f'unexpected version token: {token}')
                bad = request(proc, 'modify_file_versioned', path='sample.txt',
                              content='must-not-write', expected_version='invalid')
                require(status(bad) != 'success', f'invalid token accepted: {bad}')
                require(target.read_text() == 'original', 'invalid token changed target')
                modified = request(proc, 'modify_file_versioned', path='sample.txt',
                                   content='updated', expected_version=token)
                require(status(modified) == 'success', f'valid modification: {modified}')
                require(target.read_text() == 'updated', 'successful modification did not commit')
                replay = request(proc, 'modify_file_versioned', path='sample.txt',
                                 content='replay', expected_version=token)
                require(status(replay) != 'success', f'replayed token accepted: {replay}')
                require(target.read_text() == 'updated', 'replay changed target')
                fresh = request(proc, 'get_file_version', path='sample.txt')
                require(status(fresh) == 'success', f'fresh version: {fresh}')
                target.write_text('external-change', encoding='utf-8')
                stale = request(proc, 'modify_file_versioned', path='sample.txt',
                                content='stale-write', expected_version=fresh['output'])
                require(status(stale) != 'success', f'stale snapshot accepted: {stale}')
                require(target.read_text() == 'external-change', 'stale request changed target')
                missing = request(proc, 'modify_file_versioned', path='missing.txt',
                                  content='nope', expected_version='invalid')
                require(status(missing) != 'success', f'missing file modified: {missing}')
                traversal = request(proc, 'get_file_version', path='../outside.txt')
                require(status(traversal) != 'success', f'traversal accepted: {traversal}')
                print('PASS: Linux E2 same-process version observation, commit, replay rejection, stale conflict, and invalid-path rejection')
            finally:
                proc.stdin.close()
                try:
                    proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.wait(timeout=5)


if __name__ == '__main__':
    main()
