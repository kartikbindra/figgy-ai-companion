"""Exercise real ASGI routes, SQLite transactions, worker lifecycle and SSE."""
import json
import asyncio
from pathlib import Path
import tempfile
import threading
import time
import unittest

from fastapi.testclient import TestClient
from services.api.app import create_app
from services.inference.runtime import GenerationResult
from services.personality.compose import Personality
from services.storage.store import Store


class TestRuntime:
    def __init__(self, blocking=False, activation=True):
        self.model_lock = threading.RLock()
        self.release = threading.Event()
        self.entered = threading.Event()
        self.calls = []
        self.blocking, self.activation = blocking, activation
        self.state = 'ready'

    def status(self):
        return {'state': self.state, 'model_id': 'test-only', 'max_input_tokens': 768,
                'capabilities': {'activation': self.activation}, 'profile': {'hash': 'test'}}

    def count_tokens(self, messages):
        return sum(len(m.content.split()) for m in messages) + 10

    def generate(self, messages, strength, max_tokens, cancel, on_text):
        self.calls.append((messages, strength, max_tokens))
        self.entered.set()
        on_text('Test fixture response.')
        if self.blocking:
            self.release.wait(3)
        return GenerationResult(4, .01, 'stopped' if cancel.is_set() else 'end')


class UnifiedTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.path = Path(self.directory.name) / 'state.sqlite3'
        self.runtime = TestRuntime()
        self.app = create_app(runtime=self.runtime, database=self.path)
        self.client_context = TestClient(self.app, base_url='http://127.0.0.1:8791')
        self.client = self.client_context.__enter__()

    def tearDown(self):
        self.runtime.release.set()
        self.client_context.__exit__(None, None, None)
        self.directory.cleanup()

    def conversation(self):
        response = self.client.post('/api/v2/conversations', json={})
        self.assertEqual(response.status_code, 201)
        return response.json()['id']

    def turn(self, identifier, message='Hello.', key='test-turn-key'):
        return self.client.post(f'/api/v2/conversations/{identifier}/turns', json={'message': message}, headers={'Idempotency-Key': key})

    def done(self, identifier):
        for _ in range(200):
            response = self.client.get(f'/api/v2/jobs/{identifier}')
            result = response.json()
            if result['status'] in ('complete', 'stopped', 'failed'):
                return result
            time.sleep(.005)
        self.fail('Worker did not finish.')

    def test_chat_is_structured_persistent_and_idempotent(self):
        identifier = self.conversation()
        response = self.turn(identifier, 'My name is Ada.')
        self.assertEqual(response.status_code, 202, response.text)
        result = self.done(response.json()['id'])
        self.assertEqual(result['status'], 'complete')
        self.assertEqual(self.runtime.calls[0][0][0].role, 'system')
        self.assertEqual(self.runtime.calls[0][0][-1].role, 'user')
        self.assertEqual(self.runtime.calls[0][1], 0)
        self.assertEqual(self.turn(identifier, 'My name is Ada.').json()['id'], result['id'])
        self.assertEqual(len(self.runtime.calls), 1)
        self.assertEqual(self.turn(identifier, 'Different input.').status_code, 409)
        self.assertEqual(self.client.get('/api/v2/memories').json()['memories'][0]['content'], 'Name: Ada')
        memory = self.client.get('/api/v2/memories').json()['memories'][0]
        self.assertEqual(self.client.delete(f"/api/v2/memories/{memory['id']}").status_code, 200)
        self.assertEqual(self.client.get('/api/v2/memories').json()['memories'], [])
        persisted = Store(self.path).conversation(identifier)
        self.assertEqual(persisted['turns'][0]['outputs']['reply'], 'Test fixture response.')

    def test_frozen_settings_and_conversation_reservation_survive_stop(self):
        self.runtime.blocking = True
        identifier = self.conversation()
        other = self.conversation()
        first = self.turn(identifier).json()
        self.assertTrue(self.runtime.entered.wait(1))
        self.assertEqual(self.turn(identifier, key='second-key-123').status_code, 409)
        settings = Personality.parse({'persona': 'existentialist'}).document()
        self.assertEqual(self.client.put(f'/api/v2/conversations/{identifier}/settings', json=settings).status_code, 200)
        self.assertEqual(json.loads(first['request']['provenance'])['settings']['persona'], 'dark_comedian')
        second = self.turn(other, key='other-key-123').json()
        self.client.delete(f"/api/v2/jobs/{first['id']}")
        self.assertEqual(self.turn(identifier, key='third-key-123').status_code, 409)
        self.assertEqual(len(self.runtime.calls), 1)
        self.runtime.release.set()
        self.assertEqual(self.done(first['id'])['status'], 'stopped')
        self.done(second['id'])
        self.assertEqual(self.client.get('/api/v2/memories').json()['memories'], [])
        next_turn = self.turn(identifier, key='fourth-key-123').json()
        self.done(next_turn['id'])
        messages = self.runtime.calls[-1][0]
        self.assertIn('Existentialist', messages[0].content)
        self.assertEqual(len(messages), 2)  # stopped turn excluded from history

    def test_four_conditions_share_one_queue_and_do_not_write_memory(self):
        response = self.client.post('/api/v2/experiments', json={'prompt': 'My name is Fixture.', 'settings': {'strength': .25}}, headers={'Idempotency-Key': 'experiment-key'})
        self.assertEqual(response.status_code, 202, response.text)
        job = self.done(response.json()['id'])
        self.assertEqual(list(job['outputs']), ['baseline', 'prompt', 'activation', 'combined'])
        self.assertEqual([call[1] for call in self.runtime.calls], [0, 0, .25, .25])
        self.assertEqual([call[0][0].role for call in self.runtime.calls], ['user', 'system', 'user', 'system'])
        self.assertEqual(self.runtime.calls[0][0], self.runtime.calls[2][0])
        self.assertEqual(self.runtime.calls[1][0], self.runtime.calls[3][0])
        self.assertEqual(self.client.get('/api/v2/memories').json()['memories'], [])
        self.assertEqual(self.client.get('/api/v2/conversations').json()['conversations'], [])
        events = self.client.get(f"/api/v2/jobs/{job['id']}/events")
        self.assertIn('event: snapshot', events.text)
        self.assertIn('"status": "complete"', events.text)
        self.assertEqual(self.app.state.manager.jobs[job['id']].subscribers, 0)

    def test_context_rejection_does_not_reserve_a_turn(self):
        identifier = self.conversation()
        response = self.turn(identifier, 'long ' * 790)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(len(self.app.state.manager.jobs), 0)
        self.assertEqual(self.turn(identifier, 'Fits now.').status_code, 202)

    def test_http_policy_and_validation(self):
        self.assertEqual(self.client.get('/api/runtime', headers={'Host': 'attacker.example'}).status_code, 403)
        self.assertEqual(self.client.post('/api/runtime/load', json={}, headers={'Origin': 'https://example.com'}).status_code, 403)
        self.assertEqual(self.client.post('/api/runtime/load', content='{}').status_code, 415)
        self.assertEqual(self.client.post('/api/runtime/load', json={'x': 'z' * 33000}).status_code, 413)
        self.assertEqual(self.client.post('/api/runtime/load', content='[]', headers={'Content-Type': 'application/json'}).status_code, 400)
        self.assertEqual(self.client.post('/api/runtime/load', json={'device': {}}).status_code, 400)
        self.assertIn("frame-ancestors 'none'", self.client.get('/api/runtime').headers['Content-Security-Policy'])
        self.assertEqual(self.client.get('/%2e%2e/%2e%2e/pyproject.toml').status_code, 404)

    def test_unsupported_activation_is_rejected(self):
        self.runtime.activation = False
        response = self.client.post('/api/v2/experiments', json={'prompt': 'Hello', 'settings': {'strength': .5}}, headers={'Idempotency-Key': 'experiment-key'})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.client.post('/api/comparisons', json={'prompt': 'Hello'}, headers={'Idempotency-Key': 'original-key'}).status_code, 400)

    def test_v1_comparison_contract_still_works(self):
        response = self.client.post('/api/comparisons', json={'prompt': 'Hello'}, headers={'Idempotency-Key': 'original-key'})
        result = self.done(response.json()['id'])
        self.assertEqual(result['schema_version'], 1)
        self.assertEqual(set(result['outputs']), {'original', 'remix'})

    def test_personality_validation(self):
        for weights in ({'bad': 1}, {'dark_comedian': -1}, {'dark_comedian': float('nan')}, {'dark_comedian': 0}, {'dark_comedian': True}):
            with self.assertRaises(ValueError):
                Personality.parse({'fusion': weights})
        settings = Personality.parse({'fusion': {'dark_comedian': .6, 'existentialist': .2}})
        self.assertAlmostEqual(dict(settings.fusion)['dark_comedian'], .75)

    def test_partial_output_is_checkpointed_and_marked_interrupted_on_restart(self):
        self.runtime.blocking = True
        identifier = self.conversation()
        job = self.turn(identifier).json()
        self.assertTrue(self.runtime.entered.wait(1))
        with self.app.state.manager.condition:
            snapshot = self.app.state.manager.snapshot(self.app.state.manager.jobs[job['id']])
            self.app.state.store.checkpoint(snapshot)
        # Simulate recovery reading a prior process's unfinalized turn.
        recovered = Store(self.path).conversation(identifier)['turns'][0]
        self.assertEqual(recovered['status'], 'interrupted')
        self.assertEqual(recovered['outputs']['reply'], 'Test fixture response.')

    def test_sse_generator_releases_subscription_on_disconnect(self):
        from services.api.app import stream
        self.runtime.blocking = True
        identifier = self.conversation()
        job = self.turn(identifier).json()
        class Request:
            headers = {}
            query_params = {}
            async def is_disconnected(self):
                return False
        async def check():
            response = stream(Request(), self.app.state.manager, job['id'])
            await anext(response.body_iterator)
            self.assertEqual(self.app.state.manager.jobs[job['id']].subscribers, 1)
            await response.body_iterator.aclose()
            self.assertEqual(self.app.state.manager.jobs[job['id']].subscribers, 0)
        asyncio.run(check())
        self.assertEqual(self.turn(identifier, key='overlap-after-disconnect').status_code, 409)


if __name__ == '__main__':
    unittest.main()
