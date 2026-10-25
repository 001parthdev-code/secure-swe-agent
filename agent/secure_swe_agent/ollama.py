"""Ollama JSON decision adapter. No third-party Python dependencies."""
import json
from urllib import request, error


class ModelError(RuntimeError):
    pass


class Ollama:
    def __init__(self, model='qwen3.5:4b', url='http://127.0.0.1:11434', timeout=120):
        # Fixed local endpoint by default; not an arbitrary remote URL from model output.
        self.model, self.url, self.timeout = model, url.rstrip('/'), timeout

    def decide(self, messages: list[dict]) -> dict:
        payload = json.dumps({'model': self.model, 'messages': messages,
                              'stream': False, 'format': 'json',
                              'options': {'temperature': 0}}).encode('utf-8')
        req = request.Request(self.url + '/api/chat', data=payload,
                              headers={'Content-Type': 'application/json'}, method='POST')
        try:
            with request.urlopen(req, timeout=self.timeout) as response:
                raw = json.load(response)
            content = raw['message']['content']
            decision = json.loads(content)
        except (error.URLError, TimeoutError, ValueError, KeyError, TypeError) as exc:
            raise ModelError('Ollama request or JSON decision failed') from exc
        if not isinstance(decision, dict):
            raise ModelError('Model decision must be a JSON object')
        return decision
