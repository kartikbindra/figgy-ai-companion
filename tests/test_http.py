import io
import json
from email.message import Message
from types import SimpleNamespace
import unittest
from services.inference.jobs import JobManager
from services.inference.runtime import LocalRuntime
from services.inference.server import make_handler


class HttpContractTests(unittest.TestCase):
    def setUp(self):
        self.runtime = LocalRuntime()
        self.manager = JobManager(self.runtime)
    def tearDown(self):
        self.manager.close()
        self.manager.worker.join(1)
    def request(self, method, path, body=b'', headers=None):
        handler_type = make_handler(self.runtime, self.manager)
        handler = handler_type.__new__(handler_type)
        handler.path, handler.command = path, method
        handler.requestline = f'{method} {path} HTTP/1.1'
        handler.request_version = 'HTTP/1.1'
        handler.server = SimpleNamespace(server_port=8791)
        handler.rfile, handler.wfile = io.BytesIO(body), io.BytesIO()
        handler.headers = Message()
        for key, value in {'Host': '127.0.0.1:8791', 'Content-Type': 'application/json',
                           'Content-Length': str(len(body)), **(headers or {})}.items():
            handler.headers[key] = value
        getattr(handler, f'do_{method}')()
        raw = handler.wfile.getvalue()
        head, content = raw.split(b'\r\n\r\n', 1)
        return int(head.split(b' ')[1]), json.loads(content), head
    def test_runtime_can_report_setup_without_model_packages(self):
        status, data, headers = self.request('GET', '/api/runtime')
        self.assertEqual(status, 200)
        self.assertEqual(data['state'], 'not_loaded')
        self.assertTrue(data['local_only'])
        self.assertIn(b"frame-ancestors 'none'", headers)
    def test_untrusted_origin_and_rebound_host_are_rejected(self):
        for headers in ({'Origin': 'https://untrusted.example'}, {'Host': 'attacker.example:8791'}):
            status, _, _ = self.request('POST', '/api/runtime/load', b'{}', headers)
            self.assertEqual(status, 403)
            self.assertEqual(self.runtime.state, 'not_loaded')
    def test_form_submission_and_oversized_body_are_rejected(self):
        self.assertEqual(self.request('POST', '/api/runtime/load', b'{}', {'Content-Type': 'text/plain'})[0], 415)
        self.assertEqual(self.request('POST', '/api/runtime/load', b'{}', {'Content-Length': '40000'})[0], 413)
    def test_path_traversal_does_not_expose_source(self):
        self.assertEqual(self.request('GET', '/%2e%2e/%2e%2e/pyproject.toml')[0], 404)
    def test_not_ready_model_never_substitutes_fake_output(self):
        body = json.dumps({'prompt': 'ordinary prompt'}).encode()
        status, _, _ = self.request('POST', '/api/comparisons', body, {'Idempotency-Key': 'test-key-123'})
        self.assertEqual(status, 503)
        self.assertEqual(len(self.manager.jobs), 0)
    def test_nonfinite_and_unknown_request_fields_are_rejected(self):
        for payload in ({'prompt': 'x', 'strength': float('nan')}, {'prompt': 'x', 'model_path': '/tmp/model'}):
            status, _, _ = self.request('POST', '/api/comparisons', json.dumps(payload).encode())
            self.assertEqual(status, 400)


if __name__ == '__main__':
    unittest.main()
