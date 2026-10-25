"""Persistent JSON-lines Enforcer client; mutation requires explicit trusted opt-in."""
import json
import os
import sys
from pathlib import Path
import queue
import subprocess
import threading


class EnforcerError(RuntimeError):
    pass


class EnforcerClient:
    def __init__(self, executable: Path, workspace: Path, timeout: float = 10, *, trusted_exclusive: bool = False):
        if trusted_exclusive and sys.platform != "linux":
            raise EnforcerError("trusted-exclusive mode is Linux-only")
        self.trusted_exclusive = trusted_exclusive
        self.executable = Path(executable).resolve(strict=True)
        self.workspace = Path(workspace).resolve(strict=True)
        self.timeout = timeout
        self.process = None
        self.responses = queue.Queue()

    def __enter__(self):
        env = os.environ.copy()
        env['ENFORCER_WORKSPACE'] = str(self.workspace)
        # Never propagate prototype mutation/execution toggles to the agent-owned subprocess.
        for key in ('ENFORCER_TRUSTED_EXCLUSIVE_WORKSPACE', 'ENFORCER_ENABLE_EXECUTION',
                    'ENFORCER_EXECUTION_UID', 'ENFORCER_EXECUTION_GID'):
            env.pop(key, None)
        if self.trusted_exclusive:
            env["ENFORCER_TRUSTED_EXCLUSIVE_WORKSPACE"] = "1"
        self.process = subprocess.Popen([str(self.executable)], stdin=subprocess.PIPE,
                                        stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                                        text=True, encoding='utf-8', env=env, bufsize=1)
        def reader():
            try:
                for line in self.process.stdout:
                    self.responses.put(line)
            finally:
                self.responses.put(None)
        threading.Thread(target=reader, daemon=True).start()
        return self

    def request(self, action: str, **fields) -> dict:
        if self.process is None or self.process.poll() is not None:
            raise EnforcerError('Enforcer not running')
        request = json.dumps({'action': action, **fields}, ensure_ascii=False)
        if len(request.encode('utf-8')) > 64 * 1024:
            raise EnforcerError('Request too large')
        try:
            self.process.stdin.write(request + '\n')
            self.process.stdin.flush()
            line = self.responses.get(timeout=self.timeout)
        except (BrokenPipeError, OSError, queue.Empty) as exc:
            self.close()
            raise EnforcerError('Enforcer transport failed or timed out') from exc
        if line is None:
            raise EnforcerError('Enforcer exited without a response')
        try:
            response = json.loads(line)
        except json.JSONDecodeError as exc:
            raise EnforcerError('Invalid Enforcer response') from exc
        if not isinstance(response, dict) or not isinstance(response.get('status'), str):
            raise EnforcerError('Malformed Enforcer response')
        return response

    def read_file(self, path: str) -> dict:
        return self.request('read_file', path=path)

    def get_file_version(self, path: str) -> dict:
        return self.request('get_file_version', path=path)

    def modify_file_versioned(self, path: str, content: str, token: str) -> dict:
        if not self.trusted_exclusive:
            raise EnforcerError('mutation disabled for this client')
        return self.request('modify_file_versioned', path=path, content=content,
                            expected_version=token)

    def close(self):
        if self.process is not None:
            if self.process.poll() is None:
                self.process.terminate()
                try:
                    self.process.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    self.process.kill()
                    self.process.wait()
            for pipe in (self.process.stdin, self.process.stdout):
                if pipe:
                    pipe.close()
            self.process = None

    def __exit__(self, *_):
        self.close()
