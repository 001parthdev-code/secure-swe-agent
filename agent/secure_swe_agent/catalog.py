"""Trusted, operator-curated repository index. Never scan host files as the model."""
import json
from pathlib import PurePosixPath

MAX_FILES = 200
MAX_CATALOG_BYTES = 32 * 1024


def valid_path(path: str) -> bool:
    if not isinstance(path, str) or not path or len(path) > 512:
        return False
    if '\\' in path or '\x00' in path or ':' in path:
        return False
    parts = path.split('/')
    return all(part not in ('', '.', '..') for part in parts) and not path.startswith('/')


def load_catalog(manifest) -> list[str]:
    """Manifest is supplied by the trusted operator, never by model output."""
    if manifest.stat().st_size > MAX_CATALOG_BYTES:
        raise ValueError('manifest too large')
    raw = json.loads(manifest.read_text(encoding='utf-8'))
    if not isinstance(raw, dict) or set(raw) != {'files'} or not isinstance(raw['files'], list):
        raise ValueError('manifest must contain only a files array')
    files = raw['files']
    if len(files) > MAX_FILES or any(not valid_path(p) for p in files):
        raise ValueError('invalid or oversized file catalog')
    if len(set(files)) != len(files):
        raise ValueError('duplicate catalog paths')
    return files
