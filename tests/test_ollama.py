import io
import json
import threading
import unittest
from unittest.mock import patch
from services.inference.work import Message
from services.providers.ollama import OllamaRuntime


class OllamaTests(unittest.TestCase):
    def test_model_probe_requires_exact_installed_model_and_records_digest(self):
        runtime = OllamaRuntime()
        installed = {'models': [{'name': runtime.model + ':latest', 'digest': 'test-digest', 'details': {'quantization_level': 'Q4'}}]}
        with patch('services.providers.ollama.urlopen', return_value=io.BytesIO(json.dumps(installed).encode())):
            runtime._load()
        self.assertEqual(runtime.status()['state'], 'ready')
        self.assertEqual(runtime.status()['model_revision'], 'test-digest')
        self.assertFalse(runtime.status()['capabilities']['activation'])
        runtime.status()['profile']['details']['quantization_level'] = 'bad'
        self.assertEqual(runtime.profile['details']['quantization_level'], 'Q4')

    def test_ollama_payload_preserves_roles_limits_and_stream_completion(self):
        runtime = OllamaRuntime()
        runtime.profile = {'model': 'test-only'}
        chunks = [{'message': {'content': 'Fixture'}}, {'done': True, 'eval_count': 2, 'done_reason': 'length'}]
        response = io.BytesIO(b'\n'.join(json.dumps(c).encode() for c in chunks))
        outputs = []
        with patch('services.providers.ollama.urlopen', return_value=response) as call:
            result = runtime.generate((Message('system', 'Persona'), Message('user', 'Hello')), 0, 16, threading.Event(), outputs.append)
        payload = json.loads(call.call_args.args[0].data)
        self.assertEqual(payload['messages'][0]['role'], 'system')
        self.assertEqual(payload['options']['num_predict'], 16)
        self.assertEqual(payload['options']['temperature'], 0)
        self.assertEqual(payload['keep_alive'], 0)
        self.assertEqual(outputs, ['Fixture'])
        self.assertEqual(result.tokens, 2)
        self.assertEqual(result.stop_reason, 'length')

    def test_truncated_stream_is_failure_and_activation_is_rejected(self):
        runtime = OllamaRuntime()
        runtime.profile = {'model': 'test-only'}
        with patch('services.providers.ollama.urlopen', return_value=io.BytesIO(b'')):
            with self.assertRaisesRegex(RuntimeError, 'without a completion'):
                runtime.generate((Message('user', 'Hello'),), 0, 16, threading.Event(), lambda text: None)
        with self.assertRaisesRegex(ValueError, 'activation'):
            runtime.generate((Message('user', 'Hello'),), .5, 16, threading.Event(), lambda text: None)
