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
function boot({ storageFails = false, expired = false } = {}) {
  const errors = [], streams = [], requests = [], copied = [];
  const console = new VirtualConsole(); console.on('jsdomError', error => errors.push(error));
  const dom = new JSDOM(html, { url: 'http://127.0.0.1:8791/', runScripts: 'dangerously', pretendToBeVisual: true,
    virtualConsole: console, beforeParse(window) {
      window.HTMLDialogElement.prototype.showModal = function () { this.setAttribute('open', ''); };
      window.TextEncoder = TextEncoder; window.TextDecoder = TextDecoder;
      Object.defineProperty(window.navigator, 'clipboard', { value: { writeText: async text => copied.push(text) } });
      window.fetch = async (path, options) => {
        requests.push([path, options]);
        if (expired && path === `/api/comparisons/${fixture.id}` && !options?.method)
          return { ok: false, status: 404, json: async () => ({ error: 'Comparison expired' }) };
        const value = path === '/api/runtime' ? runtime : path === '/api/examples' ? { examples: [] } :
          options?.method === 'DELETE' ? { ...fixture, status: 'stopping' } : fixture;
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
test('a failed recipe save preserves the dialog and reports the storage failure', async () => {
  const app = boot({ storageFails: true });
  try {
    await until(() => textButton(app.document, 'Save this mix'));
    textButton(app.document, 'Save this mix').click();
    await until(() => app.document.querySelector('dialog[open]'));
    app.document.querySelector('form').dispatchEvent(new app.dom.window.Event('submit', { bubbles: true, cancelable: true }));
    await until(() => app.document.querySelector('.toast'));
    assert.match(app.document.querySelector('.toast').textContent, /storage is full or unavailable/);
    assert.ok(app.document.querySelector('dialog[open]'));
    assert.doesNotMatch(app.document.querySelector('.toast').textContent, /Mix saved/);
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
