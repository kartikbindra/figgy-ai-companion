"""Unified loopback API. Inference stays on the existing dedicated worker."""
from contextlib import asynccontextmanager
import asyncio
import json

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from starlette.concurrency import run_in_threadpool

from services.conversations.service import CompanionService
from services.inference.contracts import ComparisonRequest, recipe_metadata
from services.inference.jobs import JobError, JobManager, TERMINAL
from services.inference.runtime import LocalRuntime, ROOT, STATE_DIR
from services.personality.compose import catalog
from services.storage.store import Store


class LocalPolicy:
    def __init__(self, app, port):
        self.app, self.port = app, port

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http':
            return await self.app(scope, receive, send)
        headers = dict(scope['headers'])
        hosts = {f'127.0.0.1:{self.port}'.encode(), f'localhost:{self.port}'.encode()}
        origin = headers.get(b'origin')
        async def secure_send(message):
            if message['type'] == 'http.response.start':
                message['headers'].extend([
                    (b'cache-control', b'no-store'), (b'x-content-type-options', b'nosniff'),
                    (b'referrer-policy', b'no-referrer'),
                    (b'content-security-policy', b"default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'self'")])
            await send(message)
        if headers.get(b'host') not in hosts or (origin and origin not in {b'http://' + h for h in hosts}):
            return await JSONResponse({'error': 'This app accepts requests from its local origin only.'}, 403)(scope, receive, secure_send)
        if scope['method'] in ('POST', 'PUT', 'PATCH'):
            if headers.get(b'content-type', b'').split(b';')[0].strip() != b'application/json':
                return await JSONResponse({'error': 'Send application/json.'}, 415)(scope, receive, secure_send)
            try:
                length = int(headers.get(b'content-length', b'0'))
            except ValueError:
                length = -1
            if length < 0 or length > 32768:
                return await JSONResponse({'error': 'Request exceeds the local body limit.'}, 413)(scope, receive, secure_send)
            body = bytearray()
            while True:
                event = await receive()
                if event['type'] == 'http.disconnect':
                    return
                body.extend(event.get('body', b''))
                if len(body) > 32768:
                    return await JSONResponse({'error': 'Request exceeds the local body limit.'}, 413)(scope, receive, secure_send)
                if not event.get('more_body'):
                    break
            sent = False
            original_receive = receive
            async def buffered_receive():
                nonlocal sent
                if not sent:
                    sent = True
                    return {'type': 'http.request', 'body': bytes(body)}
                return await original_receive()
            receive = buffered_receive
        await self.app(scope, receive, secure_send)


def create_app(*, runtime=None, database=None, web_root=None, port=8791):
    @asynccontextmanager
    async def lifespan(app):
        app.state.runtime = runtime or LocalRuntime()
        app.state.store = Store(database or STATE_DIR / 'companion.sqlite3')
        # Four sequential CPU legs can exceed the old two-leg ten-minute limit.
        app.state.manager = JobManager(app.state.runtime, deadline=3600,
                                       on_finish=app.state.store.finish, on_progress=app.state.store.checkpoint)
        app.state.companion = CompanionService(app.state.runtime, app.state.manager, app.state.store)
        try:
            yield
        finally:
            app.state.manager.close()
            # Retain ownership until generation exits and hooks have been removed.
            await run_in_threadpool(app.state.manager.worker.join)
            await run_in_threadpool(app.state.manager.monitor.join)
            loader = getattr(app.state.runtime, 'load_thread', None)
            if loader:
                await run_in_threadpool(loader.join)

    app = FastAPI(title='Neuron DJ + Figgy', lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)
    app.add_middleware(LocalPolicy, port=port)

    @app.exception_handler(JobError)
    async def job_error(request, exc):
        return JSONResponse({'error': str(exc)}, exc.status)

    @app.exception_handler(ValueError)
    async def invalid(request, exc):
        return JSONResponse({'error': str(exc)}, 400)

    @app.get('/health')
    def health():
        status = app.state.runtime.status()
        return {'api': 'ready', 'inference': status['state'], 'provider': status.get('provider', 'transformers')}

    @app.api_route('/api/{path:path}', methods=['GET', 'POST', 'PUT', 'DELETE'])
    async def api(path: str, request: Request):
        body = None
        if request.method in ('POST', 'PUT'):
            try:
                body = await request.json()
            except (ValueError, UnicodeError):
                raise ValueError('Send a valid JSON object.')
            if not isinstance(body, dict):
                raise ValueError('Send a JSON object.')
        parts = path.split('/')
        manager = app.state.manager
        if request.method == 'GET' and len(parts) == 4 and parts[:2] == ['v2', 'jobs'] and parts[3] == 'events':
            return stream(request, manager, parts[2])
        if request.method == 'GET' and len(parts) == 3 and parts[0] == 'comparisons' and parts[2] == 'events':
            return stream(request, manager, parts[1])
        result, status = await run_in_threadpool(dispatch, app, request.method, parts, body, request.headers.get('Idempotency-Key', ''))
        return JSONResponse(result, status)

    app.mount('/', StaticFiles(directory=web_root or ROOT / 'apps/web/dist', html=True), name='web')
    return app


def dispatch(app, method, parts, body, key):
    runtime, manager, store = app.state.runtime, app.state.manager, app.state.store
    path = '/'.join(parts)
    if method == 'GET':
        if path == 'runtime':
            return runtime.status(), 200
        if path == 'recipe':
            return recipe_metadata(), 200
        if path == 'examples':
            examples = []
            try:
                doc = json.loads((STATE_DIR / 'examples.json').read_text())
                if isinstance(doc, dict) and doc.get('recorded') is True and isinstance(doc.get('comparisons'), list):
                    examples = [item for item in doc['comparisons'] if isinstance(item, dict)][:3]
            except (ValueError, OSError):
                pass
            return {'examples': examples}, 200
        if len(parts) == 2 and parts[0] == 'comparisons':
            return manager.get(parts[1]), 200
        if parts[:2] == ['v2', 'jobs'] and len(parts) == 3:
            return manager.get(parts[2]), 200
        if path == 'v2/personas':
            return {'personas': catalog()}, 200
        if path == 'v2/conversations':
            return {'conversations': store.conversations()}, 200
        if parts[:2] == ['v2', 'conversations'] and len(parts) == 3:
            with manager.condition:
                document = store.conversation(parts[2])
                document['turns'] = [manager.snapshot(manager.jobs[t['id']]) if t['id'] in manager.jobs else t for t in document['turns']]
                return document, 200
        if path == 'v2/memories':
            return {'memories': store.memories()}, 200
    if method == 'POST':
        if path == 'runtime/load':
            if set(body) - {'device'} or body.get('device') not in (None, 'cpu', 'mps'):
                raise ValueError('Model loading accepts an optional cpu or mps device.')
            runtime.load_async(device=body.get('device'))
            return runtime.status(), 202
        if path == 'comparisons':
            if not runtime.status().get('capabilities', {}).get('activation', True):
                raise ValueError('The original comparison recipe requires the Transformers provider.')
            return manager.submit(ComparisonRequest.parse(body), key), 202
        if path == 'v2/conversations':
            if set(body) - {'title'}:
                raise ValueError('Only a conversation title is accepted.')
            return store.create(body.get('title', 'New conversation')), 201
        if parts[:2] == ['v2', 'conversations'] and len(parts) == 4 and parts[3] == 'turns':
            return app.state.companion.chat(parts[2], body, key), 202
        if path == 'v2/experiments':
            return app.state.companion.experiment(body, key), 202
    if method == 'PUT' and parts[:2] == ['v2', 'conversations'] and len(parts) == 4 and parts[3] == 'settings':
        with manager.condition:
            return store.settings(parts[2], body), 200
    if method == 'DELETE':
        if parts[:2] == ['v2', 'memories'] and len(parts) == 3:
            try:
                identifier = int(parts[2])
            except ValueError:
                raise ValueError('Invalid memory ID.')
            store.delete_memory(identifier)
            return {'deleted': True}, 200
        if len(parts) == 2 and parts[0] == 'comparisons':
            return manager.cancel(parts[1]), 200
        if parts[:2] == ['v2', 'jobs'] and len(parts) == 3:
            return manager.cancel(parts[2]), 200
    raise JobError(404, 'Endpoint not found.')


def stream(request, manager, identifier):
    try:
        after = int(request.headers.get('Last-Event-ID') or request.query_params.get('after', '0'))
    except ValueError:
        raise JobError(400, 'Invalid event cursor.')
    with manager.condition:
        manager.get(identifier)
        job = manager.jobs[identifier]
        if not 0 <= after <= job.sequence:
            raise JobError(400, 'Invalid event cursor.')
        if job.subscribers >= 3:
            raise JobError(429, 'Too many streams for this job.')
    async def events():
        nonlocal after
        # Admission and finally live inside the generator, including cancellation.
        with manager.condition:
            if job.subscribers >= 3:
                return
            job.subscribers += 1
        try:
            heartbeat = 0
            while not await request.is_disconnected():
                with manager.condition:
                    pending = [e for e in job.events if e['id'] > after]
                    done = job.status in TERMINAL
                for event in pending:
                    after = event['id']
                    yield f'id: {after}\nevent: snapshot\ndata: {json.dumps(event, ensure_ascii=False)}\n\n'
                if done:
                    return
                if heartbeat % 40 == 0:
                    yield ': heartbeat\n\n'
                heartbeat += 1
                await asyncio.sleep(.25)
        finally:
            import time
            with manager.condition:
                job.subscribers -= 1
                job.last_seen = time.monotonic()
    return StreamingResponse(events(), media_type='text/event-stream', headers={'X-Accel-Buffering': 'no'})
