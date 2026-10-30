"""Local, operator-only A7 integration gateway (first live read/proposal slice).

Not internet-facing. Does not grant filesystem writes, Git or GitHub access.
"""
from __future__ import annotations

import json
import hashlib
import tempfile
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


class ApprovalRequest(BaseModel):
    revision: int = Field(ge=1)
    proposal_sha256: str = Field(min_length=64, max_length=64)


class CommitApprovalRequest(BaseModel):
    revision: int = Field(ge=1)
    staged_sha256: str = Field(pattern=r'^[0-9a-f]{64}$')
    message: str = Field(min_length=1, max_length=120)


class PublishApprovalRequest(BaseModel):
    revision: int = Field(ge=1)
    approval_sha256: str = Field(pattern=r'^[0-9a-f]{64}$')


class RejectRequest(BaseModel):
    revision: int = Field(ge=1)


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
        # Operator-owned fixed destination; never accept a model- or browser-selected repo.
        self.github_repo = os.environ.get('SWE_GITHUB_REPO', '')
        self.publish_base = os.environ.get('SWE_GITHUB_BASE', 'main')
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
    pending: dict[str, bytes] = {}

    def authorize(token: str | None) -> None:
        if not token or not secrets.compare_digest(token, config.token):
            raise HTTPException(status_code=401, detail='operator authentication required')

    @app.get('/api/health')
    def health(x_operator_token: str | None = Header(default=None)):
        authorize(x_operator_token)
        return {'status': 'ready', 'mode': 'live_approved_fixture', 'enforcer': 'configured'}

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
            if active and tasks[active]['status'] not in ('published', 'rejected', 'failed'):
                raise HTTPException(status_code=409, detail='current workflow must be completed or reconciled first')
            task_id = uuid.uuid4().hex
            task = {'id': task_id, 'title': payload.description, 'repository': 'calculator-demo',
                    'branch': 'not created', 'status': 'analyzing', 'model': 'qwen3.5:4b',
                    'revision': 1, 'events': [{'id': uuid.uuid4().hex, 'timestamp': 'now',
                    'title': 'Live Qwen analysis started', 'detail': 'Enforcer read-only tool access',
                    'kind': 'pending'}], 'changes': [], 'tests': None, 'prUrl': None, 'commitReview': None, 'publishReview': None}
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
            proposal_bytes = result.stdout
            fingerprint = hashlib.sha256(proposal_bytes).hexdigest()
            change_view = {'path': change['path'], 'before': '', 'after': '',
                           'explanation': change.get('rationale', ''),
                           'diff': change.get('diff', '')}
            with lock:
                task = tasks[task_id]
                task['status'] = 'awaiting_change_approval'
                task['revision'] += 1
                task['changes'] = [change_view]
                task['proposal_sha256'] = fingerprint
                pending[task_id] = proposal_bytes
                task['events'].append({'id': uuid.uuid4().hex, 'timestamp': 'now',
                    'title': 'Real proposal generated', 'detail': 'Exact proposal ready for operator review',
                    'kind': 'success'})
        except (Exception,) as exc:
            with lock:
                task = tasks[task_id]
                task['status'] = 'failed'
                task['revision'] += 1
                task['events'].append({'id': uuid.uuid4().hex, 'timestamp': 'now',
                    'title': 'Analysis failed', 'detail': str(exc)[:240], 'kind': 'error'})

    @app.post('/api/tasks/{task_id}/reject')
    def reject(task_id: str, payload: RejectRequest,
               x_operator_token: str | None = Header(default=None)):
        authorize(x_operator_token)
        with lock:
            task = tasks.get(task_id)
            if task is None:
                raise HTTPException(404, 'task not found')
            if task['status'] != 'awaiting_change_approval' or task['revision'] != payload.revision:
                raise HTTPException(409, 'stale or invalid approval state')
            task['status'] = 'rejected'
            task['revision'] += 1
            pending.pop(task_id, None)
            task['events'].append({'id': uuid.uuid4().hex, 'timestamp': 'now',
                'title': 'Change rejected', 'detail': 'No file modification performed', 'kind': 'info'})
            return dict(task)

    @app.post('/api/tasks/{task_id}/approve')
    def approve(task_id: str, payload: ApprovalRequest,
                x_operator_token: str | None = Header(default=None)):
        authorize(x_operator_token)
        with lock:
            task = tasks.get(task_id)
            if task is None:
                raise HTTPException(404, 'task not found')
            if task['status'] != 'awaiting_change_approval' or task['revision'] != payload.revision:
                raise HTTPException(409, 'stale or invalid approval state')
            raw = pending.get(task_id)
            if raw is None or hashlib.sha256(raw).hexdigest() != payload.proposal_sha256 or not secrets.compare_digest(payload.proposal_sha256, task['proposal_sha256']):
                raise HTTPException(409, 'proposal fingerprint mismatch')
            # This API intentionally supports a single in-flight operation in one process.
            task['status'] = 'applying'
            task['revision'] += 1
            task['events'].append({'id': uuid.uuid4().hex, 'timestamp': 'now',
                'title': 'Exact proposal approved', 'detail': 'Linux Enforcer application started', 'kind': 'pending'})
            pending.pop(task_id, None)
        threading.Thread(target=apply_task, args=(task_id, raw), daemon=True).start()
        with lock:
            return dict(tasks[task_id])

    def apply_task(task_id: str, raw: bytes) -> None:
        # The trusted workflow checks branch, clean Git tree, base SHA and
        # version token before requesting any modification from the Enforcer.
        from . import workflow
        try:
            # Proposal artifact is outside the approved repository workspace.
            with tempfile.TemporaryDirectory(prefix='swe-live2-proposal-') as folder:
                proposal_path = Path(folder) / 'proposal.json'
                proposal_path.write_bytes(raw)
                workflow.prepare(config.repo, proposal_path, 'live-' + task_id[:12])
                result = workflow.apply(config.repo, proposal_path,
                                        hashlib.sha256(raw).hexdigest(), config.enforcer)
            verification = result.get('verification')
            with lock:
                task = tasks[task_id]
                task['revision'] += 1
                task['branch'] = 'agent/task-live-' + task_id[:12]
                if result.get('status') == 'verified' and verification and verification.get('verified'):
                    task['status'] = 'awaiting_commit_approval'
                    output = verification.get('output', '')
                    match = re.search(r'Ran (\d+) tests? in ', output)
                    passed = int(match.group(1)) if match else 0
                    task['tests'] = {'passed': passed, 'failed': 0, 'output': output[:8192]}
                    task['events'].append({'id': uuid.uuid4().hex, 'timestamp': 'now',
                        'title': 'Approved change verified', 'detail': 'Trusted calculator regression suite passed', 'kind': 'success'})
                else:
                    task['status'] = 'needs_reconciliation'
                    task['events'].append({'id': uuid.uuid4().hex, 'timestamp': 'now',
                        'title': 'Modification requires operator inspection',
                        'detail': 'Verification or Enforcer operation did not confirm success', 'kind': 'error'})
        except BaseException as exc:
            with lock:
                task = tasks[task_id]
                task['status'] = 'needs_reconciliation'
                task['revision'] += 1
                task['events'].append({'id': uuid.uuid4().hex, 'timestamp': 'now',
                    'title': 'Operation outcome uncertain',
                    'detail': str(exc)[:200] + '; inspect repository before retrying', 'kind': 'error'})


    def event(task: dict, title: str, detail: str, kind: str = 'info') -> None:
        task['events'].append({'id': uuid.uuid4().hex, 'timestamp': 'now',
                               'title': title, 'detail': detail[:240], 'kind': kind})

    @app.post('/api/tasks/{task_id}/review-commit')
    def review_commit(task_id: str, x_operator_token: str | None = Header(default=None)):
        authorize(x_operator_token)
        from . import workflow
        with lock:
            task = tasks.get(task_id)
            if task is None:
                raise HTTPException(404, 'task not found')
            if task['status'] != 'awaiting_commit_approval':
                raise HTTPException(409, 'task is not ready for commit review')
            # Prevent another request from overlapping staging and review.
            task['status'] = 'reviewing_commit'
            task['revision'] += 1
        try:
            result = workflow.review_commit(config.repo, 'workspace/calculator/calculator.py')
            with lock:
                task['commitReview'] = {'diff': result['diff_untrusted'],
                                        'staged_sha256': result['staged_sha256']}
                task['status'] = 'awaiting_commit_approval'
                task['revision'] += 1
                event(task, 'Git commit review ready', 'Review exact staged diff', 'success')
                return dict(task)
        except Exception as exc:
            with lock:
                task['status'] = 'needs_reconciliation'
                task['revision'] += 1
                event(task, 'Commit review failed', str(exc), 'error')
            raise HTTPException(409, 'commit review failed; operator inspection required') from None

    @app.post('/api/tasks/{task_id}/approve-commit')
    def approve_commit(task_id: str, payload: CommitApprovalRequest,
                       x_operator_token: str | None = Header(default=None)):
        authorize(x_operator_token)
        from . import workflow
        with lock:
            task = tasks.get(task_id)
            if task is None:
                raise HTTPException(404, 'task not found')
            review = task.get('commitReview')
            if (task['status'] != 'awaiting_commit_approval' or
                    task['revision'] != payload.revision or not review or
                    not secrets.compare_digest(review['staged_sha256'], payload.staged_sha256)):
                raise HTTPException(409, 'stale or unreviewed commit approval')
            task['status'] = 'committing'
            task['revision'] += 1
        try:
            result = workflow.commit(config.repo, 'workspace/calculator/calculator.py',
                                     payload.staged_sha256, payload.message)
            with lock:
                task['status'] = 'committed'
                task['revision'] += 1
                task['commit'] = result['commit']
                task['commitReview'] = None
                event(task, 'Approved commit created', result['commit'], 'success')
                return dict(task)
        except Exception as exc:
            with lock:
                task['status'] = 'needs_reconciliation'
                task['revision'] += 1
                event(task, 'Commit outcome uncertain', str(exc), 'error')
            raise HTTPException(409, 'commit outcome uncertain; operator inspection required') from None

    @app.post('/api/tasks/{task_id}/review-publish')
    def review_publish(task_id: str, x_operator_token: str | None = Header(default=None)):
        authorize(x_operator_token)
        from . import workflow
        if not config.github_repo:
            raise HTTPException(409, 'SWE_GITHUB_REPO is not configured')
        with lock:
            task = tasks.get(task_id)
            if task is None:
                raise HTTPException(404, 'task not found')
            if task['status'] != 'committed':
                raise HTTPException(409, 'task must be committed first')
            task['status'] = 'reviewing_publish'
            task['revision'] += 1
        title = 'Fix calculator subtraction bug'
        body = 'Approved Secure SWE Agent calculator correction; trusted regression tests passed.'
        try:
            plan = workflow.review_publish(config.repo, config.github_repo,
                                           config.publish_base, title, body)
            if plan['head'] != task.get('commit'):
                raise RuntimeError('published commit does not match approved task commit')
            with lock:
                task['publishReview'] = {k: plan[k] for k in
                    ('github_repo', 'branch', 'head', 'base', 'title', 'body', 'approval_sha256')}
                task['status'] = 'awaiting_publish_approval'
                task['revision'] += 1
                event(task, 'GitHub publication review ready', 'Review destination and commit', 'success')
                return dict(task)
        except Exception as exc:
            with lock:
                task['status'] = 'needs_reconciliation'
                task['revision'] += 1
                event(task, 'Publication review failed', str(exc), 'error')
            raise HTTPException(409, 'publication review failed; operator inspection required') from None

    @app.post('/api/tasks/{task_id}/approve-publish')
    def approve_publish(task_id: str, payload: PublishApprovalRequest,
                        x_operator_token: str | None = Header(default=None)):
        authorize(x_operator_token)
        from . import workflow
        with lock:
            task = tasks.get(task_id)
            if task is None:
                raise HTTPException(404, 'task not found')
            plan = task.get('publishReview')
            if (task['status'] != 'awaiting_publish_approval' or
                    task['revision'] != payload.revision or not plan or
                    not secrets.compare_digest(plan['approval_sha256'], payload.approval_sha256)):
                raise HTTPException(409, 'stale or unreviewed publication approval')
            task['status'] = 'publishing'
            task['revision'] += 1
        try:
            result = workflow.publish(config.repo, plan['github_repo'], plan['base'],
                                      plan['title'], plan['body'], plan['approval_sha256'])
            if result.get('status') not in ('pull_request_created', 'pull_request_exists'):
                raise RuntimeError('GitHub broker did not confirm publication')
            with lock:
                task['status'] = 'published'
                task['revision'] += 1
                task['prUrl'] = result['url']
                task['publishReview'] = None
                event(task, 'GitHub PR confirmed', result['url'], 'success')
                return dict(task)
        except Exception as exc:
            with lock:
                task['status'] = 'needs_reconciliation'
                task['revision'] += 1
                event(task, 'Publication outcome uncertain', str(exc), 'error')
            raise HTTPException(409, 'publication outcome uncertain; inspect GitHub before retrying') from None


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
