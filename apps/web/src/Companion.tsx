import React, { useEffect, useRef, useState } from 'react';
import type { Runtime } from './types';
import './companion.css';

type Settings = { persona: string; fusion: Record<string, number>; intensity: number; mood: boolean; memory: boolean; strength: number; max_tokens: number };
type Persona = { id: string; name: string; description: string };
type Work = { id: string; sequence: number; status: string; request: { prompt: string; kind: string; conversation_id?: string; provenance: string }; outputs: Record<string, string>; error: string | null; queue_position: number | null; metrics: Record<string, { seconds: number; tokens: number }> };
type Conversation = { id: string; title: string; settings: Settings; turns: Work[] };
const defaults: Settings = { persona: 'dark_comedian', fusion: {}, intensity: .85, mood: true, memory: true, strength: 0, max_tokens: 128 };
const labels: Record<string, string> = { baseline: 'Baseline', prompt: 'Prompt only', activation: 'Activation only', combined: 'Combined' };
const finished = (status: string) => ['complete', 'stopped', 'failed', 'interrupted'].includes(status);
async function api(path: string, method = 'GET', body?: unknown, key?: string) {
  const response = await fetch(path, { method, headers: { ...(body !== undefined ? { 'Content-Type': 'application/json' } : {}), ...(key ? { 'Idempotency-Key': key } : {}) }, body: body === undefined ? undefined : JSON.stringify(body) });
  const value = await response.json();
  if (!response.ok) throw new Error(value.error || 'The local service could not complete this request.');
  return value;
}
function readActive() { try { return sessionStorage.getItem('figgy.conversation'); } catch { return null; } }

export function Companion({ mode, runtime, setup }: { mode: string; runtime: Runtime; setup: () => void }) {
  const [personas, setPersonas] = useState<Persona[]>([]);
  const [conversations, setConversations] = useState<{ id: string; title: string }[]>([]);
  const [conversation, setConversation] = useState<Conversation | null>(null);
  const [settings, setSettings] = useState<Settings>(defaults);
  const [memories, setMemories] = useState<{ id: number; content: string }[]>([]);
  const [message, setMessage] = useState('');
  const [experimentPrompt, setExperimentPrompt] = useState('');
  const [conditions, setConditions] = useState(['baseline', 'prompt', 'activation', 'combined']);
  const [job, setJob] = useState<Work | null>(null);
  const [experiment, setExperiment] = useState<Work | null>(null);
  const [error, setError] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [loaded, setLoaded] = useState(false);
  const pending = useRef<{ fingerprint: string; key: string } | null>(null);
  const sequence = useRef(0);
  const busyRef = useRef(false);
  const busy = submitting || (!!job && !finished(job.status));
  const activation = runtime.capabilities?.activation !== false;
  useEffect(() => {
    if (!activation) { setConditions(['baseline', 'prompt']); setSettings(previous => ({ ...previous, strength: 0 })); }
  }, [activation]);
  async function loadConversation(id: string) {
    const value: Conversation = await api(`/api/v2/conversations/${id}`);
    setConversation(value); setSettings(value.settings);
    try { sessionStorage.setItem('figgy.conversation', id); } catch { /* Optional convenience. */ }
    const active = value.turns.find(t => !finished(t.status));
    if (active) { sequence.current = 0; setJob(active); }
  }
  async function refreshLists() {
    const [p, c, m] = await Promise.all([api('/api/v2/personas'), api('/api/v2/conversations'), api('/api/v2/memories')]);
    setPersonas(p.personas); setConversations(c.conversations); setMemories(m.memories);
  }
  useEffect(() => {
    if (mode === 'studio' || location.protocol === 'file:') return;
    let alive = true;
    refreshLists().then(async () => {
      if (!loaded && alive) {
        const id = readActive();
        if (id) await loadConversation(id).catch(() => {});
        setLoaded(true);
      }
    }).catch(e => { if (alive) setError(e.message); });
    return () => { alive = false; };
  }, [mode]);
  useEffect(() => {
    if (!job || finished(job.status)) return;
    const id = job.id;
    const source = new EventSource(`/api/v2/jobs/${id}/events?after=${sequence.current}`);
    let alive = true;
    const update = (next: Work) => {
      if (!alive) return;
      setJob(next);
      if (next.request.kind === 'experiment') setExperiment(next);
      if (finished(next.status)) {
        source.close();
        if (next.request.conversation_id) loadConversation(next.request.conversation_id).catch(e => setError(e.message));
        refreshLists().catch(e => setError(e.message));
      }
    };
    source.addEventListener('snapshot', event => {
      try {
        const value = JSON.parse((event as MessageEvent).data);
        if (value.job.id === id && value.id > sequence.current) { sequence.current = value.id; update(value.job); }
      } catch { setError('Could not read the stream. Reload to reconnect.'); }
    });
    source.onerror = () => {
      api(`/api/v2/jobs/${id}`).then(update).catch(e => {
        if (!alive) return;
        source.close(); setError(e.message);
        setJob(previous => previous?.id === id ? { ...previous, status: 'interrupted', error: 'The service restarted or this job expired. Received text is preserved.' } : previous);
      });
    };
    return () => { alive = false; source.close(); };
  }, [job?.id]);
  async function create() {
    try {
      const value = await api('/api/v2/conversations', 'POST', { title: `Conversation ${conversations.length + 1}` });
      setConversation(value); setSettings(value.settings); setMessage(''); setJob(null);
      try { sessionStorage.setItem('figgy.conversation', value.id); } catch { /* Optional. */ }
      await refreshLists();
    } catch (e) { setError((e as Error).message); }
  }
  async function submit(isExperiment: boolean) {
    if (busyRef.current || busy) return;
    busyRef.current = true; setSubmitting(true); setError('');
    try {
      if (runtime.state !== 'ready') { setup(); return; }
      let current = conversation;
      if (!isExperiment && !current) {
        current = await api('/api/v2/conversations', 'POST', { title: message.trim().slice(0, 60) || 'New conversation' });
        setConversation(current);
        if (current) { try { sessionStorage.setItem('figgy.conversation', current.id); } catch { /* Optional. */ } }
      }
      if (!isExperiment && current) await api(`/api/v2/conversations/${current.id}/settings`, 'PUT', settings);
      const path = isExperiment ? '/api/v2/experiments' : `/api/v2/conversations/${current!.id}/turns`;
      const body = isExperiment ? { prompt: experimentPrompt, settings, conditions } : { message };
      const fingerprint = JSON.stringify([path, body]);
      if (pending.current?.fingerprint !== fingerprint) pending.current = { fingerprint, key: crypto.randomUUID() };
      const value = await api(path, 'POST', body, pending.current.key);
      pending.current = null; sequence.current = 0; setJob(value);
      if (isExperiment) setExperiment(value); else setMessage('');
      await refreshLists();
    } catch (e) { setError((e as Error).message); }
    finally { busyRef.current = false; setSubmitting(false); }
  }
  async function saveSettings() {
    if (!conversation) return;
    try { setSettings(await api(`/api/v2/conversations/${conversation.id}/settings`, 'PUT', settings)); setError('Settings saved for the next turn.'); }
    catch (e) { setError((e as Error).message); }
  }
  async function stop() {
    if (!job) return;
    try { setJob(await api(`/api/v2/jobs/${job.id}`, 'DELETE')); }
    catch (e) { setError((e as Error).message); }
  }
  const displayed = conversation ? [...conversation.turns.filter(t => t.id !== job?.id), ...(job?.request.conversation_id === conversation.id ? [job] : conversation.turns.filter(t => t.id === job?.id))] : [];
  return <section className="companion-shell" hidden={mode === 'studio'} aria-label={mode === 'methods' ? 'Method comparisons' : mode === 'memory' ? 'Persistent memory' : 'Companion chat'}>
    <div className="companion-heading"><div><span className="eyebrow">FIGGY + NEURON DJ</span><h1>{mode === 'methods' ? 'Compare the methods.' : mode === 'memory' ? 'What Figgy remembers.' : 'A conversation with character.'}</h1><p>{mode === 'methods' ? 'One checkpoint, matched decoding, two to four sequential conditions. History and memory are excluded.' : mode === 'memory' ? 'Explicit facts learned from completed turns. Stored on this Mac.' : 'Five personas, persistent conversations, and an optional activation intervention.'}</p></div><button className="button secondary" onClick={setup}>Local setup</button></div>
    {location.protocol === 'file:' && <p className="companion-notice">Start the local service and open its HTTP address to use chat and memory.</p>}
    {error && <p className="companion-notice" role="alert">{error}</p>}
    {mode === 'memory' ? <div className="memory-list">{!memories.length && <p>No facts saved yet. Memory is learned selectively when it is enabled for a completed turn.</p>}{memories.map(m => <article key={m.id}><p>{m.content}</p><button className="button secondary" onClick={async () => { try { await api(`/api/v2/memories/${m.id}`, 'DELETE'); await refreshLists(); } catch (e) { setError((e as Error).message); } }}>Delete memory</button></article>)}</div> : <div className="companion-grid">
      <aside className="persona-controls" aria-label="Personality controls">
        {mode === 'companion' && <><label>Conversation<select aria-label="Conversation" disabled={busy} value={conversation?.id || ''} onChange={e => loadConversation(e.target.value).catch(err => setError(err.message))}><option value="" disabled>Choose a conversation</option>{conversations.map(c => <option key={c.id} value={c.id}>{c.title}</option>)}</select></label><button className="button secondary" disabled={busy} onClick={create}>New conversation</button></>}
        <label>Personality<select aria-label="Personality" value={settings.persona} onChange={e => setSettings({ ...settings, persona: e.target.value, fusion: {} })}>{personas.map(p => <option value={p.id} key={p.id}>{p.name}</option>)}</select></label>
        <label>Prompt intensity · {settings.intensity.toFixed(2)}<input aria-label="Prompt intensity" type="range" min="0" max="1" step=".05" value={settings.intensity} onChange={e => setSettings({ ...settings, intensity: +e.target.value })}/></label>
        <details><summary>Blend personalities</summary><p>Positive weights are normalized together.</p>{personas.map(p => <label key={p.id}>{p.name}<input aria-label={`${p.name} fusion weight`} type="range" min="0" max="1" step=".1" value={settings.fusion[p.id] || 0} onChange={e => { const fusion = { ...settings.fusion, [p.id]: +e.target.value }; Object.keys(fusion).forEach(k => { if (!fusion[k]) delete fusion[k]; }); setSettings({ ...settings, fusion }); }}/></label>)}</details>
        <label>Activation strength · {settings.strength.toFixed(2)}×<input aria-label="Activation strength" disabled={!activation} type="range" min="0" max="1" step=".05" value={settings.strength} onChange={e => setSettings({ ...settings, strength: +e.target.value })}/></label><small>Experimental. Independent of prompt intensity.</small>
        <label>Output tokens<select aria-label="Output tokens" value={settings.max_tokens} onChange={e => setSettings({ ...settings, max_tokens: +e.target.value })}>{[16, 64, 128, 256].map(v => <option key={v}>{v}</option>)}</select></label>
        <label className="check-field"><input type="checkbox" checked={settings.mood} onChange={e => setSettings({ ...settings, mood: e.target.checked })}/> Adapt prompt to mood</label>
        {mode === 'companion' && <><label className="check-field"><input type="checkbox" checked={settings.memory} onChange={e => setSettings({ ...settings, memory: e.target.checked })}/> Use and learn memory</label><button className="button secondary" disabled={!conversation} onClick={saveSettings}>Save conversation settings</button></>}
        <p className="provider-label">{runtime.model_id}<br/>{runtime.state === 'ready' ? 'Model connected' : runtime.message}</p>
      </aside>
      <div className="conversation-body">
        {mode === 'companion' ? <><div className="turn-list" aria-live="polite">{!displayed.length && <p className="empty-chat">Start a conversation. Your history stays on this Mac.</p>}{displayed.map(turn => <article className="chat-turn" key={turn.id}><div className="user-turn"><span>You</span><p>{turn.request.prompt}</p></div><div className="assistant-turn"><span>Figgy · {turn.status}</span><p>{turn.outputs.reply || 'Waiting for generation…'}</p>{turn.error && <p role="alert">{turn.error}</p>}<details><summary>Settings used</summary><pre>{JSON.stringify(JSON.parse(turn.request.provenance), null, 2)}</pre></details></div></article>)}</div><form onSubmit={e => { e.preventDefault(); submit(false); }}><label htmlFor="chat-message">Message Figgy</label><textarea id="chat-message" value={message} maxLength={4000} required onChange={e => setMessage(e.target.value)} placeholder="Tell Figgy what’s on your mind…"/><div className="composer-actions"><button className="button primary" disabled={busy || !message.trim() || location.protocol === 'file:'}>{submitting ? 'Submitting…' : runtime.state !== 'ready' ? 'Open setup' : 'Send message'}</button>{busy && <button type="button" className="button secondary" onClick={stop}>Stop generation</button>}</div></form></> : <><fieldset className="condition-picker"><legend>Conditions · select two to four</legend>{Object.entries(labels).map(([key, label]) => <label className="check-field" key={key}><input type="checkbox" checked={conditions.includes(key)} disabled={!activation && ['activation', 'combined'].includes(key)} onChange={e => setConditions(e.target.checked ? [...conditions, key] : conditions.filter(v => v !== key))}/>{label}</label>)}</fieldset><form onSubmit={e => { e.preventDefault(); submit(true); }}><label htmlFor="method-prompt">Experiment prompt</label><textarea id="method-prompt" value={experimentPrompt} required maxLength={4000} onChange={e => setExperimentPrompt(e.target.value)}/><div className="composer-actions"><button className="button primary" disabled={busy || conditions.length < 2 || !experimentPrompt.trim() || location.protocol === 'file:'}>Run method comparison</button>{busy && <button type="button" className="button secondary" onClick={stop}>Stop generation</button>}</div></form>{experiment && <><p className="companion-notice">{experiment.status}{experiment.queue_position ? ` · Queue position ${experiment.queue_position}` : ''}{experiment.error ? ` · ${experiment.error}` : ''}</p><div className="method-results">{Object.entries(experiment.outputs).map(([name, output]) => <article key={name}><h2>{labels[name]}</h2><p>{output || 'Waiting for this condition…'}</p>{experiment.metrics[name] && <small>{experiment.metrics[name].tokens} tokens · {experiment.metrics[name].seconds}s</small>}</article>)}</div><button className="button secondary" disabled={!finished(experiment.status)} onClick={() => { const anchor = document.createElement('a'); const url = URL.createObjectURL(new Blob([JSON.stringify({ kind: 'neuron-dj-experiment', schema_version: 2, recorded: true, experiment }, null, 2)], { type: 'application/json' })); anchor.href = url; anchor.download = 'experiment.json'; anchor.click(); setTimeout(() => URL.revokeObjectURL(url), 1000); }}>Export recorded experiment</button></>}</>}
      </div>
    </div>}
  </section>;
}
