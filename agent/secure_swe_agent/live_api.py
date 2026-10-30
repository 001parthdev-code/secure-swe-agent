"""Local, operator-only A7 integration gateway (first live read/proposal slice).

Not internet-facing. Does not grant filesystem writes, Git or GitHub access.
"""
from __future__ import annotations

import json
import os
import re
import secrets
import subprocess
import sys
import threading
import uuid
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field


class StartRequest(BaseModel):
    description: str = Field(min_length=8, max_length=1200)


class LiveConfig:
    def __init__(self, repo: Path, enforcer: Path, token: str, origin: str):
        self.repo = repo.resolve(strict=True)
        self.enforcer = enforcer.resolve(strict=True)
        if not self.enforcer.is_file() or not self.repo.is_dir():
            raise ValueError('invalid trusted paths')
        if not token or len(token) < 24:
            raise ValueError('set a random API token of at least 24 characters')
        if not re.fullmatch(r'http://127\.0\.0\.1:\d{2,5}', origin):
            raise ValueError('origin must be an exact local Vite origin')
        self.token, self.origin = token, origin
        self.workspace = self.repo / 'workspace'
        self.fixture = self.workspace / 'calculator' / 'calculator.py'
        if (not self.fixture.is_file() or self.fixture.is_symlink()
                or self.workspace.is_symlink()):
            raise ValueError('trusted calculator fixture missing or linked')
        if not self.fixture.resolve().is_relative_to(self.workspace.resolve()):
            raise ValueError('fixture escapes workspace')


def create_app(config: LiveConfig) -> FastAPI:
    app = FastAPI(title='Secure SWE Agent local live API', docs_url=None, redoc_url=None,
                  openapi_url=None)
    app.add_middleware(CORSMiddleware, allow_origins=[config.origin],
                       allow_credentials=False, allow_methods=['GET', 'POST'],
                       allow_headers=['X-Operator-Token', 'Content-Type'])
    lock = threading.Lock()
    tasks: dict[str, dict[str, Any]] = {}
    active: str | None = None

    def authorize(token: str | None) -> None:
        if not token or not secrets.compare_digest(token, config.token):
            raise HTTPException(status_code=401, detail='operator authentication required')

    @app.get('/api/health')
    def health(x_operator_token: str | None = Header(default=None)):
        authorize(x_operator_token)
        return {'status': 'ready', 'mode': 'live_readonly', 'enforcer': 'configured'}

    @app.get('/api/tasks/current')
    def current(x_operator_token: str | None = Header(default=None)):
        authorize(x_operator_token)
        with lock:
            return dict(tasks[active]) if active else {'status': 'no_task'}

    @app.post('/api/tasks')
    def start(payload: StartRequest, x_operator_token: str | None = Header(default=None)):
        nonlocal active
        authorize(x_operator_token)
        if not re.search(r'\bsubtract(?:ion)?\b', payload.description, re.I):
            raise HTTPException(status_code=422, detail='Only the trusted subtraction fixture is supported')
        with lock:
            if active and tasks[active]['status'] == 'analyzing':
                raise HTTPException(status_code=409, detail='another analysis is in progress')
            task_id = uuid.uuid4().hex
            task = {'id': task_id, 'title': payload.description, 'repository': 'calculator-demo',
                    'branch': 'not created', 'status': 'analyzing', 'model': 'qwen3.5:4b',
                    'revision': 1, 'events': [{'id': uuid.uuid4().hex, 'timestamp': 'now',
                    'title': 'Live Qwen analysis started', 'detail': 'Enforcer read-only tool access',
                    'kind': 'pending'}], 'changes': [], 'tests': None, 'prUrl': None}
            tasks[task_id] = task
            active = task_id
        thread = threading.Thread(target=analyze, args=(task_id,), daemon=True)
        thread.start()
        return task

    def analyze(task_id: str) -> None:
        # Fixed argv and approved file; no shell and no model-selected executable/path.
        command = [sys.executable, str(Path(__file__).resolve().parents[1] / 'main.py'),
                   tasks[task_id]['title'], '--workspace', str(config.workspace),
                   '--enforcer', str(config.enforcer), '--file', 'calculator/calculator.py',
                   '--model', 'qwen3.5:4b', '--propose']
        try:
            result = subprocess.run(command, stdin=subprocess.DEVNULL, capture_output=True,
                                    timeout=150, check=False, env={**os.environ,
                                    'PYTHONDONTWRITEBYTECODE': '1'})
            if result.returncode:
                raise RuntimeError('Qwen/Enforcer proposal process failed')
            if len(result.stdout) > 4 * 1024 * 1024:
                raise RuntimeError('proposal exceeds response limit')
            from .approval import load_proposal
            try:
                raw_proposal = json.loads(result.stdout)
            except (ValueError, UnicodeDecodeError) as exc:
                raise RuntimeError('agent returned invalid proposal JSON') from exc
            if raw_proposal.get('status') == 'no_change':
                raise RuntimeError('Qwen proposed no source change; check whether the fixture is already fixed')
            if raw_proposal.get('status') == 'invalid_proposal':
                raise RuntimeError('Qwen did not produce one valid approved-file change')
            proposal = load_proposal(result.stdout)
            change = proposal['changes'][0]
            if change['path'] != 'calculator/calculator.py':
                raise RuntimeError('proposal selected unauthorized file')
            import hashlib
            actual = hashlib.sha256(config.fixture.read_bytes()).hexdigest()
            if actual != change['base_sha256']:
                raise RuntimeError('source changed while proposal was generated')
            change_view = {'path': change['path'], 'before': '', 'after': '',
                           'explanation': change.get('rationale', ''),
                           'diff': change.get('diff', '')}
            with lock:
                task = tasks[task_id]
                task['status'] = 'awaiting_change_approval'
                task['revision'] += 1
                task['changes'] = [change_view]
                task['events'].append({'id': uuid.uuid4().hex, 'timestamp': 'now',
                    'title': 'Real proposal generated', 'detail': 'Read-only; application disabled in this increment',
                    'kind': 'success'})
        except (Exception,) as exc:
            with lock:
                task = tasks[task_id]
                task['status'] = 'failed'
                task['revision'] += 1
                task['events'].append({'id': uuid.uuid4().hex, 'timestamp': 'now',
                    'title': 'Analysis failed', 'detail': str(exc)[:240], 'kind': 'error'})

    @app.post('/api/tasks/{task_id}/approve')
    def not_enabled(task_id: str, x_operator_token: str | None = Header(default=None)):
        authorize(x_operator_token)
        raise HTTPException(status_code=409, detail='Live modification approvals are not connected yet')

    return app


def run() -> None:
    import uvicorn
    repo = Path(os.environ['SWE_DEMO_REPO'])
    enforcer = Path(os.environ['SWE_ENFORCER_BINARY'])
    config = LiveConfig(repo, enforcer, os.environ['SWE_API_TOKEN'],
                        os.environ.get('SWE_UI_ORIGIN', 'http://127.0.0.1:5173'))
    uvicorn.run(create_app(config), host='127.0.0.1', port=8765)


if __name__ == '__main__':
    run()
