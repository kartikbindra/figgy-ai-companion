"""Optional local Ollama provider. Activation hooks are intentionally unsupported."""
import hashlib
import copy
import json
import os
import threading
import time
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

from services.inference.runtime import GenerationResult


class OllamaRuntime:
    def __init__(self):
        self.host = os.environ.get('OLLAMA_HOST', 'http://127.0.0.1:11434').rstrip('/')
        parsed = urlsplit(self.host)
        if parsed.scheme != 'http' or parsed.hostname not in ('localhost', '127.0.0.1') or parsed.username or parsed.password or parsed.path:
            raise ValueError('OLLAMA_HOST must be a local HTTP origin.')
        self.model = os.environ.get('LLM_MODEL', 'huihui_ai/qwen3-abliterated')
        self.model_lock = threading.RLock()
        self.lock = threading.RLock()
        self.state, self.message = 'not_loaded', 'Connect to the configured local Ollama model in Local setup.'
        self.profile = None
        self.load_thread = None

    def status(self):
        with self.lock:
            return {'state': self.state, 'message': self.message, 'provider': 'ollama',
                    'model_id': self.model, 'model_revision': (self.profile or {}).get('digest', 'not verified'),
                    'profile': copy.deepcopy(self.profile), 'dependencies_available': True,
                    'load_seconds': None, 'strength_cap': 0, 'max_input_tokens': 2048, 'max_output_tokens': 256,
                    'evidence': 'Different checkpoint/runtime; prompt-only experiments', 'local_only': True,
                    'capabilities': {'activation': False, 'structured_messages': True}}

    def _state(self, state, message):
        with self.lock:
            self.state, self.message = state, message

    def load_async(self, device=None):
        if device is not None:
            raise ValueError('Ollama manages its own device; choose automatic setup.')
        with self.lock:
            if self.state in ('loading', 'ready'):
                return
            self._state('loading', 'Checking the installed Ollama model…')
            self.load_thread = threading.Thread(target=self._load, daemon=True)
            self.load_thread.start()

    def _load(self):
        try:
            with urlopen(self.host + '/api/tags', timeout=5) as response:
                models = json.load(response)['models']
            configured = self.model if ':' in self.model else self.model + ':latest'
            model = next((m for m in models if m.get('name') in (self.model, configured)), None)
            if not model or not model.get('digest'):
                raise ValueError('Configured model is not installed. Pull it explicitly with Ollama first.')
            profile = {'provider': 'ollama', 'model': model['name'], 'digest': model['digest'],
                       'details': model.get('details', {}), 'thinking': False,
                       'context': 2048, 'token_budget': 'conservative UTF-8 byte estimate', 'decoding': 'greedy'}
            profile['hash'] = hashlib.sha256(json.dumps(profile, sort_keys=True).encode()).hexdigest()
            with self.lock:
                self.profile = profile
                self._state('ready', 'Local Ollama model available. Activation steering is unavailable for this provider.')
        except Exception as exc:
            self._state('error', f'Ollama connection failed: {str(exc)[:300]}')

    def count_tokens(self, messages):
        # Ollama has no tokenizer endpoint here. Reserve generously and label the estimate.
        return sum(len(m.content.encode('utf-8')) + 32 for m in messages) + 32

    def generate(self, messages, strength, max_tokens, cancel, on_text):
        if strength:
            raise ValueError('Ollama does not support this activation recipe.')
        if cancel.is_set():
            return GenerationResult(0, 0, 'stopped')
        if isinstance(messages, str):
            payload_messages = [{'role': 'user', 'content': messages}]
        else:
            payload_messages = [{'role': m.role, 'content': m.content} for m in messages]
        started = time.monotonic()
        payload = {'model': self.profile['model'], 'messages': payload_messages, 'stream': True,
                   'think': False, 'keep_alive': 0,
                   'options': {'temperature': 0, 'seed': 0, 'num_predict': max_tokens, 'num_ctx': 2048}}
        req = Request(self.host + '/api/chat', json.dumps(payload).encode(), {'Content-Type': 'application/json'})
        count, reason, complete = 0, 'end', False
        with self.model_lock, urlopen(req, timeout=120) as response:
            for line in response:
                if cancel.is_set():
                    reason = 'stopped'
                    break
                chunk = json.loads(line)
                if chunk.get('error'):
                    raise RuntimeError(chunk['error'])
                text = chunk.get('message', {}).get('content', '')
                if text:
                    on_text(text)
                if chunk.get('done'):
                    complete = True
                    count = chunk.get('eval_count', 0)
                    reason = chunk.get('done_reason', 'end')
                    break
        if not complete and not cancel.is_set():
            raise RuntimeError('Ollama stream ended without a completion record; partial output was preserved.')
        return GenerationResult(count, round(time.monotonic() - started, 3), 'stopped' if cancel.is_set() else reason)
