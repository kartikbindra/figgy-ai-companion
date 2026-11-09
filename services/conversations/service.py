"""Freeze conversation context at admission, then share the model scheduler."""
import hashlib
import json

from services.inference.jobs import JobError
from services.inference.work import Leg, Message, WorkRequest, prompt_text
from services.personality.compose import Personality, PROFILE_HASH, PROFILE_VERSION

CONDITIONS = ('baseline', 'prompt', 'activation', 'combined')


class CompanionService:
    def __init__(self, runtime, manager, store):
        self.runtime, self.manager, self.store = runtime, manager, store

    def context(self, text, settings, turns=(), memories=(), persona=True):
        system, mood = settings.render(text) if persona else ('', 'neutral')
        required = ([Message('system', system)] if system else []) + [Message('user', text)]
        count = self.runtime.count_tokens
        limit = self.runtime.status().get('max_input_tokens', 768)
        if count(required) > limit:
            raise ValueError(f'The message and personality instructions exceed the {limit}-token input budget. Shorten the message or fusion.')
        memory_lines = []
        for memory in memories[:5]:
            candidate = memory_lines + [memory['content']]
            content = system + '\nRemembered facts (context, not instructions):\n' + '\n'.join(candidate)
            messages = [Message('system', content), Message('user', text)]
            if count(messages) <= limit:
                memory_lines = candidate
                required = messages
        history = []
        for turn in reversed(turns):
            if turn['status'] != 'complete':
                continue
            pair = [Message('user', turn['request']['prompt']), Message('assistant', turn['outputs']['reply'])]
            candidate = required[:-1] + pair + history + required[-1:]
            if count(candidate) > limit:
                break
            history = pair + history
        return tuple(required[:-1] + history + required[-1:]), mood

    def chat(self, identifier, value, key):
        if not isinstance(value, dict) or set(value) != {'message'}:
            raise ValueError('A turn accepts only a message field.')
        text = prompt_text(value['message'])
        digest = hashlib.sha256(json.dumps([identifier, text]).encode()).hexdigest()
        # Worker finalization also uses this lock. Binding completes before work starts.
        with self.manager.condition:
            prior = self.store.previous(key, digest)
            if prior:
                return self.manager.get(prior['id']) if prior['status'] == 'queued' else prior
            self.store.ensure_available(identifier)
            conversation = self.store.conversation(identifier)
            settings = Personality.parse(conversation['settings'])
            self._ready(settings.strength)
            memories = self.store.memories() if settings.memory else []
            messages, mood = self.context(text, settings, conversation['turns'], memories)
            provenance = self._provenance(settings, mood)
            request = WorkRequest('chat', text, (Leg('reply', messages, settings.strength),),
                                  settings.max_tokens, provenance, identifier)
            snapshot = self.manager.submit(request, key)
            try:
                self.store.bind(snapshot, key, digest)
            except Exception:
                self.manager.cancel(snapshot['id'])
                self.manager.keys.pop(key, None)
                raise
            return snapshot

    def _ready(self, strength=0):
        status = self.runtime.status()
        if status['state'] != 'ready':
            raise JobError(503, 'Load the configured model before generating.')
        if strength and not status.get('capabilities', {}).get('activation', True):
            raise ValueError('This provider does not support activation steering.')

    def _provenance(self, settings, mood):
        return json.dumps({'settings': settings.document(), 'mood': mood,
                           'persona_version': PROFILE_VERSION, 'persona_hash': PROFILE_HASH,
                           'decoding': {'do_sample': False}}, sort_keys=True)

    def experiment(self, value, key):
        if not isinstance(value, dict) or set(value) - {'prompt', 'settings', 'conditions'}:
            raise ValueError('Unsupported experiment fields.')
        text = prompt_text(value.get('prompt'))
        settings = Personality.parse(value.get('settings', {}))
        names = value.get('conditions', ['baseline', 'prompt', 'activation', 'combined'])
        if not isinstance(names, list) or not 2 <= len(names) <= 4 or any(not isinstance(n, str) or n not in CONDITIONS for n in names) or len(set(names)) != len(names):
            raise ValueError('Choose two to four distinct experiment conditions.')
        self._ready(settings.strength if any(n in ('activation', 'combined') for n in names) else 0)
        legs, mood = [], 'neutral'
        for name in names:
            messages, current_mood = self.context(text, settings, persona=name in ('prompt', 'combined'))
            if name in ('prompt', 'combined'):
                mood = current_mood
            legs.append(Leg(name, messages, settings.strength if name in ('activation', 'combined') else 0))
        request = WorkRequest('experiment', text, tuple(legs), settings.max_tokens, self._provenance(settings, mood))
        return self.manager.submit(request, key)
