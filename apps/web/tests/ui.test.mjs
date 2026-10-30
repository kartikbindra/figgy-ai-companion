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
function boot({ storageFails = false } = {}) {
  const errors = [], streams = [], requests = [];
  const console = new VirtualConsole(); console.on('jsdomError', error => errors.push(error));
  const dom = new JSDOM(html, { url: 'http://127.0.0.1:8791/', runScripts: 'dangerously', pretendToBeVisual: true,
    virtualConsole: console, beforeParse(window) {
      window.HTMLDialogElement.prototype.showModal = function () { this.setAttribute('open', ''); };
      window.TextEncoder = TextEncoder; window.TextDecoder = TextDecoder;
      window.fetch = async (path, options) => {
        requests.push([path, options]);
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
  return { dom, document: dom.window.document, errors, streams, requests };
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
