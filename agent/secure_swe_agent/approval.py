"""A3.2: explicit operator approval and Linux-only E2 application.

This is a controlled-workspace prototype, not an isolation attestation.
"""
import hashlib
import json

from .catalog import valid_path


class ApprovalError(ValueError):
    pass


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def load_proposal(raw: bytes) -> dict:
    if len(raw) > 4 * 1024 * 1024:
        raise ApprovalError('proposal too large')
    try:
        obj = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ApprovalError('invalid proposal JSON') from exc
    if not isinstance(obj, dict) or obj.get('status') != 'approval_required' or obj.get('applied') is not False:
        raise ApprovalError('not a pending proposal')
    changes = obj.get('changes')
    if not isinstance(changes, list) or len(changes) != 1:
        raise ApprovalError('A3.2 supports exactly one change per approval')
    paths = set()
    for c in changes:
        if not isinstance(c, dict):
            raise ApprovalError('invalid change')
        path, content, base = c.get('path'), c.get('new_content'), c.get('base_sha256')
        if (not isinstance(path, str) or not valid_path(path) or path in paths
                or not isinstance(content, str) or len(content.encode('utf-8')) > 1024 * 1024
                or not isinstance(base, str) or len(base) != 64
                or any(ch not in '0123456789abcdef' for ch in base)):
            raise ApprovalError('invalid change fields')
        paths.add(path)
    return obj


def apply_approved(proposal: dict, enforcer, approved_paths: set[str]) -> dict:
    """Never writes directly. Rechecks original SHA then asks E2 to commit.

    Multi-file changes are NOT atomic as a group. Stop on first failure.
    """
    changes = proposal['changes']
    if {c['path'] for c in changes} != approved_paths:
        raise ApprovalError('approval paths do not match proposal')
    results = []
    for c in changes:
        path = c['path']
        current = enforcer.read_file(path)
        if current.get('status') != 'success' or not isinstance(current.get('output'), str):
            return {'status': 'apply_failed', 'path': path, 'reason': 'read denied', 'applied': results}
        if digest(current['output'].encode('utf-8')) != c['base_sha256']:
            return {'status': 'stale_proposal', 'path': path, 'applied': results}
        version = enforcer.get_file_version(path)
        if version.get('status') != 'success' or not isinstance(version.get('output'), str):
            return {'status': 'apply_failed', 'path': path, 'reason': 'version denied', 'applied': results}
        result = enforcer.modify_file_versioned(path, c['new_content'], version['output'])
        if result.get('status') != 'success':
            return {'status': 'apply_failed', 'path': path, 'reason': result.get('status'), 'applied': results}
        verified = enforcer.read_file(path)
        if verified.get('status') != 'success' or verified.get('output') != c['new_content']:
            return {'status': 'verification_failed', 'path': path, 'applied': results + [path]}
        results.append(path)
    return {'status': 'applied', 'applied': results}
