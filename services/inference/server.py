"""Dependency-free loopback web/API server. One process owns one model worker."""
from __future__ import annotations
import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import mimetypes
from pathlib import Path
import threading
from urllib.parse import parse_qs, unquote, urlsplit

from .contracts import ComparisonRequest, recipe_metadata
from .jobs import JobError, JobManager
from .runtime import LocalRuntime, ROOT, STATE_DIR


def make_handler(runtime, manager, web_root=None):
    static = (web_root or ROOT / 'apps/web/dist').resolve()

    class Handler(BaseHTTPRequestHandler):
        protocol_version = 'HTTP/1.1'

        def log_message(self, *args):
            pass  # Prompts, outputs, IDs and request paths are not written to access logs.

        def _headers(self, status, content_type, length=None):
            self.send_response(status)
            self.send_header('Content-Type', content_type)
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('Referrer-Policy', 'no-referrer')
            self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'self'")
            if length is not None:
                self.send_header('Content-Length', str(length))
            self.end_headers()

        def _json(self, status, data):
            body = json.dumps(data, ensure_ascii=False, allow_nan=False).encode()
            self._headers(status, 'application/json; charset=utf-8', len(body))
            self.wfile.write(body)

        def _trusted(self):
            port = self.server.server_port
            hosts = {f'127.0.0.1:{port}', f'localhost:{port}'}
            origin = self.headers.get('Origin')
            if self.headers.get('Host') not in hosts or (origin and origin not in {f'http://{h}' for h in hosts}):
                self.close_connection = True
                self._json(403, {'error': 'This instrument accepts requests from its local origin only.'})
                return False
            return True

        def _body(self):
            if self.headers.get_content_type() != 'application/json':
                raise JobError(415, 'Send application/json.')
            try:
                length = int(self.headers.get('Content-Length', '0'))
            except ValueError:
                raise JobError(400, 'Invalid content length.')
            if not 0 < length <= 32768:
                raise JobError(413, 'Request must be between 1 and 32,768 bytes.')
            try:
                value = json.loads(self.rfile.read(length))
            except (ValueError, UnicodeError):
                raise JobError(400, 'The request is not valid JSON.')
            if not isinstance(value, dict):
                raise JobError(400, 'Send a JSON object.')
            return value

        def do_POST(self):
            if not self._trusted():
                return
            try:
                body = self._body()
                path = urlsplit(self.path).path
                if path == '/api/runtime/load':
                    if body:
                        raise JobError(400, 'Model loading accepts no options.')
                    runtime.load_async()
                    return self._json(202, runtime.status())
                if path == '/api/comparisons':
                    request = ComparisonRequest.parse(body)
                    key = self.headers.get('Idempotency-Key', '')
                    return self._json(202, manager.submit(request, key))
                raise JobError(404, 'Endpoint not found.')
            except (JobError, ValueError) as exc:
                self.close_connection = True
                self._json(getattr(exc, 'status', 400), {'error': str(exc)})

        def do_DELETE(self):
            if not self._trusted():
                return
            try:
                parts = urlsplit(self.path).path.strip('/').split('/')
                if len(parts) != 3 or parts[:2] != ['api', 'comparisons']:
                    raise JobError(404, 'Endpoint not found.')
                self._json(200, manager.cancel(parts[2]))
            except JobError as exc:
                self._json(exc.status, {'error': str(exc)})

        def do_GET(self):
            if not self._trusted():
                return
            try:
                url = urlsplit(self.path)
                if url.path == '/api/runtime':
                    return self._json(200, runtime.status())
                if url.path == '/api/recipe':
                    return self._json(200, recipe_metadata())
                if url.path == '/api/examples':
                    examples = []
                    try:
                        document = json.loads((STATE_DIR / 'examples.json').read_text())
                        if document.get('recorded') is True:
                            examples = document.get('comparisons', [])[:3]
                    except (OSError, ValueError):
                        pass
                    return self._json(200, {'examples': examples})
                parts = url.path.strip('/').split('/')
                if parts[:2] == ['api', 'comparisons'] and len(parts) == 3:
                    return self._json(200, manager.get(parts[2]))
                if parts[:2] == ['api', 'comparisons'] and len(parts) == 4 and parts[3] == 'events':
                    try:
                        cursor = int(self.headers.get('Last-Event-ID') or parse_qs(url.query).get('after', ['0'])[0])
                    except ValueError:
                        raise JobError(400, 'Invalid event cursor.')
                    stream = manager.events(parts[2], cursor)
                    sentinel = object()
                    try:
                        first = next(stream, sentinel)
                        self._headers(200, 'text/event-stream; charset=utf-8')
                        self.close_connection = True
                        def send(event):
                            if event is None:
                                self.wfile.write(b': heartbeat\n\n')
                            else:
                                data = json.dumps(event, ensure_ascii=False, allow_nan=False)
                                self.wfile.write(f'id: {event["id"]}\nevent: snapshot\ndata: {data}\n\n'.encode())
                            self.wfile.flush()
                        if first is not sentinel:
                            send(first)
                        for event in stream:
                            send(event)
                    except (BrokenPipeError, ConnectionResetError):
                        pass
                    finally:
                        stream.close()
                    return
                if url.path.startswith('/api/'):
                    raise JobError(404, 'Endpoint not found.')
                name = unquote(url.path).lstrip('/') or 'index.html'
                file = (static / name).resolve()
                if not file.is_relative_to(static) or not file.is_file():
                    raise JobError(404, 'UI file not found. Build it with npm run build.')
                body = file.read_bytes()
                content_type = mimetypes.guess_type(file.name)[0] or 'application/octet-stream'
                self._headers(200, content_type, len(body))
                self.wfile.write(body)
            except (JobError, ValueError) as exc:
                self._json(getattr(exc, 'status', 400), {'error': str(exc)})
            except (BrokenPipeError, ConnectionResetError):
                pass

    return Handler


class LocalServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def get_request(self):
        client, address = super().get_request()
        client.settimeout(30)
        return client, address


def main():
    parser = argparse.ArgumentParser(description='Neuron DJ local instrument')
    parser.add_argument('--port', type=int, default=8791)
    parser.add_argument('--load-model', action='store_true')
    args = parser.parse_args()
    runtime = LocalRuntime()
    manager = JobManager(runtime)
    server = LocalServer(('127.0.0.1', args.port), make_handler(runtime, manager))
    if args.load_model:
        runtime.load_async()
    print(f'Neuron DJ → http://127.0.0.1:{server.server_port}', flush=True)
    print('Local only. Press Ctrl+C to close the instrument.', flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        manager.close()
        server.server_close()


if __name__ == '__main__':
    main()
