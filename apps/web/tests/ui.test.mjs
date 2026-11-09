import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { JSDOM, VirtualConsole } from 'jsdom';
import { REVISION, RECIPE_ID } from '../src/data.mjs';

const html = await readFile(new URL('../dist/preview.html', import.meta.url), 'utf8');
const runtime = { state: 'ready', message: 'Test runtime only', dependencies_available: true,
  model_id: 'Qwen/Qwen3.5-4B', model_revision: REVISION, profile: { device: 'test-cpu', dtype: 'float32', hash: 'a'.repeat(64) },
  strength_cap: 1, evidence: 'test-only', load_seconds: 1 };
const fixture = { id: 'test-job-only', sequence: 1, schema_version: 1, created_at: '2026-10-30T00:00:00Z',
  status: 'queued', request: { prompt: 'Test-only prompt', strength: .5, max_tokens: 128, recipe_id: RECIPE_ID, schema_version: 1 },
  runtime, outputs: { original: '', remix: '' }, metrics: {}, error: null, queue_position: 1 };
async function until(predicate) {
  for (let i = 0; i < 80; i++) { if (predicate()) return; await new Promise(r => setTimeout(r, 10)); }
  throw new Error('UI did not reach the expected state.');
}
function textButton(document, text) {
  return [...document.querySelectorAll('button')].find(button => button.textContent.includes(text));
}
function boot({ storageFails = false, expired = false, url = 'http://127.0.0.1:8791/', examples = [], initialRuntime = runtime, unified = false } = {}) {
  const errors = [], streams = [], requests = [], copied = [];
  const console = new VirtualConsole(); console.on('jsdomError', error => errors.push(error));
  const dom = new JSDOM(html, { url, runScripts: 'dangerously', pretendToBeVisual: true,
    virtualConsole: console, beforeParse(window) {
      window.HTMLDialogElement.prototype.showModal = function () { this.setAttribute('open', ''); };
      window.TextEncoder = TextEncoder; window.TextDecoder = TextDecoder;
      Object.defineProperty(window.navigator, 'clipboard', { value: { writeText: async text => copied.push(text) } });
      window.fetch = async (path, options) => {
        requests.push([path, options]);
        if (unified && path.startsWith('/api/v2/')) {
          const settings = { persona: 'dark_comedian', fusion: {}, intensity: .85, strength: 0, mood: true, memory: true, max_tokens: 128 };
          const chat = { id: 'chat-fixture', sequence: 1, status: 'queued', request: { prompt: 'Test chat', kind: 'chat', conversation_id: 'conversation-fixture', provenance: JSON.stringify({ settings }) }, outputs: { reply: '' }, metrics: {}, error: null, queue_position: 1 };
          const value = path === '/api/v2/personas' ? { personas: [{ id: 'dark_comedian', name: 'The Dark Comedian' }, { id: 'existentialist', name: 'The Existentialist' }] } :
            path === '/api/v2/memories' ? { memories: [{ id: 1, content: '<img src=x onerror=alert(1)>' }] } :
            path === '/api/v2/conversations' && options?.method === 'POST' ? { id: 'conversation-fixture', title: 'Test conversation', settings, turns: [] } :
            path === '/api/v2/conversations' ? { conversations: [{ id: 'conversation-fixture', title: 'Test conversation' }] } :
            path.endsWith('/settings') ? JSON.parse(options.body) :
            path.endsWith('/turns') ? chat :
            path === '/api/v2/experiments' ? { ...chat, id: 'experiment-fixture', request: { ...chat.request, kind: 'experiment' }, outputs: { baseline: '', prompt: '', activation: '', combined: '' } } :
            path.includes('/jobs/') && options?.method === 'DELETE' ? { ...chat, status: 'stopping' } :
            { id: 'conversation-fixture', title: 'Test conversation', settings, turns: [] };
          return { ok: true, json: async () => structuredClone(value) };
        }
        if (expired && path === `/api/comparisons/${fixture.id}` && !options?.method)
          return { ok: false, status: 404, json: async () => ({ error: 'Comparison expired' }) };
        const value = path === '/api/runtime' ? initialRuntime : path === '/api/examples' ? { examples } :
          path === '/api/runtime/load' ? { ...runtime, state: 'loading', message: 'Calibrating persona recipe: prompt 2/6…', loading_device: 'cpu', load_elapsed_seconds: 48, stage_elapsed_seconds: 9 } : options?.method === 'DELETE' ? { ...fixture, status: 'stopping' } : fixture;
        return { ok: true, json: async () => structuredClone(value) };
      };
      window.EventSource = class extends window.EventTarget {
        constructor(url) { super(); this.url = url; streams.push(this); }
        close() { this.closed = true; }
        emit(value) { this.dispatchEvent(new window.MessageEvent('snapshot', { data: JSON.stringify(value) })); }
      };
      if (storageFails) {
        window.Storage.prototype.setItem = () => { throw new Error('Storage unavailable'); };
        window.Storage.prototype.getItem = () => { throw new Error('Storage unavailable'); };
      }
    } });
  return { dom, document: dom.window.document, errors, streams, requests, copied };
}

test('the real production bundle renders without model output fixtures', async () => {
  const app = boot();
  try {
    await until(() => textButton(app.document, 'Run comparison'));
    assert.match(app.document.querySelector('#root').textContent, /Turn up the other side/);
    assert.equal(app.document.querySelectorAll('.deck').length, 2);
    assert.equal(app.document.querySelectorAll('.response-text').length, 0);
    assert.equal(textButton(app.document, 'Run comparison').disabled, true);
    assert.deepEqual(app.errors, []);
  } finally { app.dom.window.close(); }
});

test('companion submits an idempotent structured turn and preserves it across tabs', async () => {
  const app = boot({ unified: true });
  try {
    await until(() => textButton(app.document, 'Companion'));
    textButton(app.document, 'Companion').click();
    await until(() => app.document.querySelector('#chat-message'));
    const textarea = app.document.querySelector('#chat-message');
    const setter = Object.getOwnPropertyDescriptor(app.dom.window.HTMLTextAreaElement.prototype, 'value').set;
    setter.call(textarea, 'Test chat'); textarea.dispatchEvent(new app.dom.window.Event('input', { bubbles: true }));
    await until(() => !textButton(app.document, 'Send message').disabled);
    textButton(app.document, 'Send message').click();
    await until(() => app.streams.some(s => s.url.includes('/api/v2/jobs/chat-fixture')));
    const submission = app.requests.find(([path]) => path.endsWith('/turns'));
    assert.equal(JSON.parse(submission[1].body).message, 'Test chat');
    assert.ok(submission[1].headers['Idempotency-Key']);
    const stream = app.streams.find(s => s.url.includes('/api/v2/jobs/chat-fixture'));
    textButton(app.document, 'Activation studio').click();
    assert.ok(!stream.closed);
    textButton(app.document, 'Companion').click();
    textButton(app.document, 'Stop generation').click();
    await until(() => app.requests.some(([path, opts]) => path.includes('/jobs/chat-fixture') && opts?.method === 'DELETE'));
    assert.deepEqual(app.errors, []);
  } finally { app.dom.window.close(); }
});

test('memory content is rendered as text and method controls use the shared API', async () => {
  const app = boot({ unified: true });
  try {
    await until(() => textButton(app.document, 'Memory'));
    textButton(app.document, 'Memory').click();
    await until(() => app.document.querySelector('.memory-list article'));
    assert.match(app.document.querySelector('.memory-list').textContent, /<img src=x/);
    assert.equal(app.document.querySelector('.memory-list img'), null);
    textButton(app.document, 'Compare methods').click();
    await until(() => app.document.querySelector('#method-prompt'));
    const textarea = app.document.querySelector('#method-prompt');
    Object.getOwnPropertyDescriptor(app.dom.window.HTMLTextAreaElement.prototype, 'value').set.call(textarea, 'Method fixture prompt');
    textarea.dispatchEvent(new app.dom.window.Event('input', { bubbles: true }));
    await until(() => !textButton(app.document, 'Run method comparison').disabled);
    textButton(app.document, 'Run method comparison').click();
    await until(() => app.requests.some(([path]) => path === '/api/v2/experiments'));
    const submitted = JSON.parse(app.requests.find(([path]) => path === '/api/v2/experiments')[1].body);
    assert.deepEqual(submitted.conditions, ['baseline', 'prompt', 'activation', 'combined']);
    assert.equal(submitted.prompt, 'Method fixture prompt');
    assert.deepEqual(app.errors, []);
  } finally { app.dom.window.close(); }
});
test('a failed recipe save preserves the dialog and reports the storage failure', async () => {
  const app = boot({ storageFails: true });
  try {
    await until(() => textButton(app.document, 'Save this mix'));
    textButton(app.document, 'Save this mix').click();
    await until(() => app.document.querySelector('dialog[open]'));
    app.document.querySelector('dialog form').dispatchEvent(new app.dom.window.Event('submit', { bubbles: true, cancelable: true }));
    await until(() => app.document.querySelector('dialog .dialog-notice'));
    assert.match(app.document.querySelector('dialog .dialog-notice').textContent, /storage is full or unavailable/);
    assert.ok(app.document.querySelector('dialog[open]'));
    assert.doesNotMatch(app.document.querySelector('dialog .dialog-notice').textContent, /Mix saved/);
  } finally { app.dom.window.close(); }
});
test('blocked session storage does not turn successful submission into a failure', async () => {
  const app = boot({ storageFails: true });
  try {
    await until(() => app.document.querySelector('#root').textContent.includes('Model connected'));
    const starter = textButton(app.document, 'Help me plan my Monday.');
    assert.ok(starter, [...app.document.querySelectorAll('button')].map(b => b.textContent).join(' | '));
    starter.click();
    await until(() => !textButton(app.document, 'Run comparison').disabled);
    textButton(app.document, 'Run comparison').click();
    await until(() => app.streams.length === 1);
    assert.equal(app.requests.filter(([, options]) => options?.method === 'POST').length, 1);
    assert.ok(textButton(app.document, 'Stop generation'));
    app.streams[0].emit({ id: 5, type: 'complete', job: { ...fixture, sequence: 5, status: 'complete',
      outputs: { original: 'Test-only original response', remix: 'Test-only modified response' },
      metrics: { original: { tokens: 4, seconds: 1, stop_reason: 'end' }, remix: { tokens: 4, seconds: 1, stop_reason: 'end' } } } });
    await until(() => app.document.querySelector('#root').textContent.includes('Comparison complete'));
    assert.equal(app.streams[0].closed, true);
    assert.match(app.document.querySelector('.original .response-text').textContent, /Test-only original/);
    assert.deepEqual(app.errors, []);
  } finally { app.dom.window.close(); }
});

async function startComparison(app) {
  await until(() => app.document.querySelector('#root').textContent.includes('Model connected'));
  textButton(app.document, 'Help me plan my Monday.').click();
  await until(() => !textButton(app.document, 'Run comparison').disabled);
  textButton(app.document, 'Run comparison').click();
  await until(() => app.streams.length === 1);
}
const completed = { ...fixture, sequence: 5, status: 'complete',
  outputs: { original: 'Original test text', remix: 'Remix test text' },
  metrics: { original: { tokens: 3, seconds: 1, stop_reason: 'end' }, remix: { tokens: 3, seconds: 1, stop_reason: 'end' } } };

test('comparison controls preserve both decks and copy the selected response', async () => {
  const app = boot();
  try {
    await startComparison(app);
    assert.ok(app.document.querySelector('.composer').compareDocumentPosition(app.document.querySelector('.deck')) & 4);
    app.streams[0].emit({ id: 5, type: 'complete', job: completed });
    await until(() => app.document.querySelector('.remix .response-text'));
    textButton(app.document, 'Remix only').click();
    await until(() => app.document.querySelector('.original').hidden);
    assert.equal(app.document.querySelector('.remix').hidden, false);
    app.document.querySelector('[aria-label="Copy remix response"]').click();
    await until(() => app.copied.length === 1);
    assert.deepEqual(app.copied, ['Remix test text']);
    textButton(app.document, 'Side by side').click();
    await until(() => !app.document.querySelector('.original').hidden);
    assert.equal(app.document.querySelector('.original .response-text').textContent, 'Original test text');
    assert.deepEqual(app.errors, []);
  } finally { app.dom.window.close(); }
});

test('run snapshots restore the composer and recent sessions reopen recorded outputs', async () => {
  const app = boot();
  try {
    await startComparison(app);
    app.streams[0].emit({ id: 5, type: 'complete', job: completed });
    await until(() => textButton(app.document, 'Restore run settings'));
    assert.match(app.document.querySelector('.run-snapshot').textContent, /Test-only prompt/);
    textButton(app.document, 'Restore run settings').click();
    await until(() => app.document.querySelector('#prompt').value === fixture.request.prompt);
    assert.equal(textButton(app.document, 'Restore run settings'), undefined);
    app.document.querySelector('.recent-runs button').click();
    await until(() => app.document.querySelector('.deck-footer').textContent.includes('Recorded output'));
    assert.equal(app.document.querySelector('.remix .response-text').textContent, 'Remix test text');
    assert.deepEqual(app.errors, []);
  } finally { app.dom.window.close(); }
});

test('an expired stream preserves partial text and releases the run controls', async () => {
  const app = boot({ expired: true });
  try {
    await startComparison(app);
    app.streams[0].emit({ id: 2, type: 'text', job: { ...fixture, sequence: 2, status: 'running-original',
      outputs: { original: 'Partial test text', remix: '' } } });
    await until(() => app.document.querySelector('.response-text'));
    await app.streams[0].onerror();
    await until(() => textButton(app.document, 'Run comparison'));
    assert.equal(textButton(app.document, 'Run comparison').disabled, false);
    assert.equal(app.streams[0].closed, true);
    assert.equal(app.document.querySelector('.original .response-text').textContent, 'Partial test text');
    assert.match(app.document.querySelector('#root').textContent, /expired or the service restarted/);
    assert.deepEqual(app.errors, []);
  } finally { app.dom.window.close(); }
});


test('clicking dialog padding keeps the form open; clicking its backdrop closes it', async () => {
  const app = boot();
  try {
    await until(() => textButton(app.document, 'Save this mix'));
    textButton(app.document, 'Save this mix').click();
    await until(() => app.document.querySelector('dialog[open]'));
    const dialog = app.document.querySelector('dialog');
    dialog.getBoundingClientRect = () => ({ left: 100, right: 500, top: 100, bottom: 500 });
    dialog.dispatchEvent(new app.dom.window.MouseEvent('click', { bubbles: true, clientX: 110, clientY: 110 }));
    await new Promise(r => setTimeout(r, 20));
    assert.ok(app.document.querySelector('dialog[open]'));
    dialog.dispatchEvent(new app.dom.window.MouseEvent('click', { bubbles: true, clientX: 50, clientY: 50 }));
    await until(() => !app.document.querySelector('dialog'));
  } finally { app.dom.window.close(); }
});

test('invalid recorded examples cannot crash the library', async () => {
  const app = boot({ examples: [null, { id: 'broken', request: { prompt: {} } }, completed] });
  try {
    await until(() => textButton(app.document, 'Library'));
    textButton(app.document, 'Library').click();
    await until(() => app.document.querySelector('dialog[open]'));
    assert.equal(app.document.querySelectorAll('.example-button').length, 1);
    assert.deepEqual(app.errors, []);
  } finally { app.dom.window.close(); }
});

test('file preview explains how to open the functional app and does not call file APIs', async () => {
  const app = boot({ url: 'file:///test/preview.html' });
  try {
    await until(() => app.document.querySelector('.preview-banner'));
    assert.match(app.document.querySelector('.preview-banner').textContent, /preview/i);
    assert.equal(app.document.querySelector('.preview-banner a').href, 'http://127.0.0.1:8791/');
    assert.equal(app.requests.length, 0);
    assert.equal(app.streams.length, 0);
  } finally { app.dom.window.close(); }
});


test('CPU recovery selection reaches the loader and progress is visible', async () => {
  const app = boot({ initialRuntime: { ...runtime, state: 'error', profile: null, message: 'Previous GPU load failed' } });
  try {
    await until(() => textButton(app.document, 'Connect local model'));
    textButton(app.document, 'Connect local model').click();
    await until(() => app.document.querySelector('.device-choice select'));
    const select = app.document.querySelector('.device-choice select');
    select.value = 'cpu';
    select.dispatchEvent(new app.dom.window.Event('change', { bubbles: true }));
    await new Promise(r => setTimeout(r, 10));
    textButton(app.document, 'Load cached model').click();
    await until(() => app.document.querySelector('.load-progress'));
    const sent = app.requests.find(([path]) => path === '/api/runtime/load');
    assert.deepEqual(JSON.parse(sent[1].body), { device: 'cpu' });
    assert.match(app.document.querySelector('.setup-status').textContent, /prompt 2\/6/);
    assert.match(app.document.querySelector('.load-progress').textContent, /CPU · 48s elapsed/);
    assert.equal(textButton(app.document, 'Loading on your Mac').disabled, true);
    assert.deepEqual(app.errors, []);
  } finally { app.dom.window.close(); }
});
