import React, { useEffect, useRef, useState } from 'react';
import { createRoot } from 'react-dom/client';
import type { Job, Recipe, Runtime } from './types';
import { REVISION, RECIPE_ID, terminal, statusText, validateRecipe, validateReplay,
  recipeLink, recipeFromHash, readStored } from './data.mjs';
import './style.css';

const emptyRuntime: Runtime = { state: 'disconnected', message: 'Connecting to the local instrument…',
  dependencies_available: false, model_id: 'Qwen/Qwen3.5-4B', model_revision: REVISION,
  profile: null, strength_cap: 1, evidence: 'Published recipe · local pilot pending', load_seconds: null };
const starters = ['Help me plan my Monday.', 'Describe yourself in three sentences.', 'Explain why the sky is blue.'];
const presets = [{ name: 'Clean', strength: 0, note: 'No intervention' },
  { name: 'Low dose', strength: .25, note: 'A quarter of the reference' },
  { name: 'Half dose', strength: .5, note: 'Start somewhere in the middle' },
  { name: 'Reference', strength: 1, note: 'The published full dose' }];

function Icon({ name, size = 18 }: { name: string; size?: number }) {
  const paths: Record<string, React.ReactNode> = {
    play: <path d="m9 5 11 7-11 7z"/>, plus: <path d="M12 5v14M5 12h14"/>,
    arrow: <path d="M4 12h16m-6-6 6 6-6 6"/>, close: <path d="m6 6 12 12M6 18 18 6"/>,
    wave: <path d="M3 12h3l2-7 4 14 4-14 2 7h3"/>, sliders: <><path d="M5 4v16M12 4v16M19 4v16"/><path d="M2 8h6m1 8h6m1-7h6"/></>,
    save: <><path d="M5 3h12l4 4v14H3V3z"/><path d="M7 3v6h10V3M7 21v-8h10v8"/></>,
    upload: <><path d="M12 16V3m-5 5 5-5 5 5M4 16v5h16v-5"/></>,
    share: <><circle cx="6" cy="12" r="3"/><circle cx="18" cy="5" r="3"/><circle cx="18" cy="19" r="3"/><path d="m9 10 6-4M9 14l6 4"/></>,
    info: <><circle cx="12" cy="12" r="9"/><path d="M12 11v6m0-10v1"/></>,
    reset: <><path d="M4 10a8 8 0 1 1 1 8M4 4v6h6"/></>,
    folder: <path d="M3 6h7l2 3h9v11H3z"/>, check: <path d="m5 12 4 4L19 6"/>,
    cpu: <><rect x="5" y="5" width="14" height="14" rx="3"/><path d="M9 1v4m6-4v4m-6 14v4m6-4v4M1 9h4m-4 6h4m14-6h4m-4 6h4M9 9h6v6H9z"/></>,
    down: <path d="m6 9 6 6 6-6"/>, stop: <rect x="6" y="6" width="12" height="12" rx="1"/>,
  };
  return <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">{paths[name] || paths.wave}</svg>;
}

async function api(path: string, options?: RequestInit) {
  const response = await fetch(path, options);
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || 'The local instrument could not complete that request.');
  return data;
}
function download(name: string, data: unknown) {
  const url = URL.createObjectURL(new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' }));
  const anchor = document.createElement('a'); anchor.href = url; anchor.download = name; anchor.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
function Modal({ title, children, onClose }: { title: string; children: React.ReactNode; onClose: () => void }) {
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => { ref.current?.showModal(); }, []);
  return <dialog ref={ref} className="dialog" onCancel={onClose} onClick={e => { if (e.target === e.currentTarget) onClose(); }} aria-label={title}>
    <div className="dialog-top"><h2>{title}</h2><button className="icon-button" onClick={onClose} aria-label="Close dialog"><Icon name="close"/></button></div>
    {children}
  </dialog>;
}

function App() {
  const [runtime, setRuntime] = useState<Runtime>(emptyRuntime);
  const [strength, setStrength] = useState(.5);
  const [maxTokens, setMaxTokens] = useState(128);
  const [prompt, setPrompt] = useState('');
  const [job, setJob] = useState<Job | null>(null);
  const [recorded, setRecorded] = useState(false);
  const [jobId, setJobId] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [connectionLost, setConnectionLost] = useState(false);
  const [panel, setPanel] = useState<string | null>(null);
  const [toast, setToast] = useState('');
  const [recipeName, setRecipeName] = useState('My half-dose mix');
  const [recipes, setRecipes] = useState<Recipe[]>(() => readStored('neuron-dj.recipes.v1', validateRecipe));
  const [savedRuns, setSavedRuns] = useState<Job[]>(() => readStored('neuron-dj.runs.v1', validateReplay, 8));
  const [examples, setExamples] = useState<Job[]>([]);
  const inputFile = useRef<HTMLInputElement>(null);
  const promptRef = useRef<HTMLTextAreaElement>(null);
  const activeRef = useRef<string | null>(null);
  const sequenceRef = useRef(0);
  const pending = useRef<{ fingerprint: string; key: string } | null>(null);
  const busy = !!job && !terminal(job.status) && !recorded;
  const changed = !!job && (strength !== job.request.strength || maxTokens !== job.request.max_tokens || prompt.trim() !== job.request.prompt);
  const selected = presets.find(p => p.strength === strength);
  const notify = (message: string) => setToast(message);

  async function refresh() {
    try { setRuntime(await api('/api/runtime')); }
    catch { setRuntime({ ...emptyRuntime, message: 'The local service is offline. Start it to reconnect.' }); }
  }
  useEffect(() => {
    refresh(); const timer = setInterval(refresh, 4000);
    api('/api/examples').then(data => setExamples(data.examples)).catch(() => {});
    try {
      const incoming = recipeFromHash(location.hash);
      if (incoming) { setStrength(incoming.strength); setMaxTokens(incoming.max_tokens); notify(`Loaded “${incoming.name}”. Nothing runs until you press Run comparison.`); }
    } catch (e) { notify((e as Error).message); }
    const id = sessionStorage.getItem('neuron-dj.active');
    if (id) api(`/api/comparisons/${id}`).then(data => {
      setJob(data); setPrompt(data.request.prompt); setStrength(data.request.strength); setMaxTokens(data.request.max_tokens);
      if (!terminal(data.status)) setJobId(id);
    }).catch(() => sessionStorage.removeItem('neuron-dj.active'));
    return () => clearInterval(timer);
  }, []);
  useEffect(() => {
    if (!toast) return;
    const timer = setTimeout(() => setToast(''), 6500); return () => clearTimeout(timer);
  }, [toast]);
  useEffect(() => {
    if (!jobId) return;
    activeRef.current = jobId;
    const source = new EventSource(`/api/comparisons/${jobId}/events?after=${sequenceRef.current}`);
    source.addEventListener('snapshot', event => {
      if (activeRef.current !== jobId) return;
      try {
        const data = JSON.parse((event as MessageEvent).data);
        if (data.job.id !== jobId || data.id <= sequenceRef.current) return;
        sequenceRef.current = data.id;
        setConnectionLost(false); setJob(data.job);
        if (terminal(data.job.status)) { source.close(); sessionStorage.removeItem('neuron-dj.active'); refresh(); }
      } catch { source.close(); notify('Could not read the response stream. Reload to reconnect to this run.'); }
    });
    source.onerror = () => { if (activeRef.current === jobId) setConnectionLost(true); };
    return () => { source.close(); if (activeRef.current === jobId) activeRef.current = null; };
  }, [jobId]);

  function applyRecipe(recipe: Recipe) {
    if (recipe.profile_hash && runtime.profile?.hash && recipe.profile_hash !== runtime.profile.hash) {
      return notify('That saved recipe belongs to a different runtime profile. Its calibration cannot be reused here.');
    }
    setStrength(recipe.strength); setMaxTokens(recipe.max_tokens);
    notify(`“${recipe.name}” is set for the next comparison.`);
  }
  function makeRecipe(name = recipeName): Recipe {
    return validateRecipe({ kind: 'neuron-dj-recipe', schema_version: 1, id: crypto.randomUUID(),
      name, recipe_id: RECIPE_ID, model_revision: REVISION, strength, max_tokens: maxTokens,
      profile_hash: typeof runtime.profile?.hash === 'string' ? runtime.profile.hash : null });
  }
  function storeRecipes(next: Recipe[]) {
    try { localStorage.setItem('neuron-dj.recipes.v1', JSON.stringify(next)); setRecipes(next); }
    catch { notify('Browser storage is full or unavailable. Export your recipe to a file instead.'); }
  }
  function saveRecipe(event: React.FormEvent) {
    event.preventDefault();
    try { storeRecipes([makeRecipe(), ...recipes].slice(0, 12)); setPanel(null); notify('Mix saved on this browser. Prompts and responses were not included.'); }
    catch (e) { notify((e as Error).message); }
  }
  function replayEnvelope(value: Job) { return { kind: 'neuron-dj-replay', schema_version: 1, recorded: true, comparison: value }; }
  function saveRun() {
    if (!job) return;
    const next = [job, ...savedRuns.filter(j => j.id !== job.id)].slice(0, 8);
    try { localStorage.setItem('neuron-dj.runs.v1', JSON.stringify(next.map(replayEnvelope))); setSavedRuns(next); notify('Comparison saved on this browser, including the prompt and both responses.'); }
    catch { notify('Browser storage is unavailable. Export this comparison instead.'); }
  }
  function viewReplay(value: Job) {
    if (busy) return notify('Stop the active run before opening a replay.');
    setJobId(null); setJob(value); setRecorded(true); setPrompt(value.request.prompt);
    setStrength(value.request.strength); setMaxTokens(value.request.max_tokens); setPanel(null);
  }
  async function importFile(file: File | undefined) {
    if (!file) return;
    if (file.size > 250000) return notify('Choose a recipe or replay smaller than 250 KB.');
    try {
      const value = JSON.parse(await file.text());
      if (value.kind === 'neuron-dj-replay') viewReplay(validateReplay(value));
      else { const recipe = validateRecipe(value); storeRecipes([recipe, ...recipes].slice(0, 12)); applyRecipe(recipe); }
    } catch (e) { notify((e as Error).message); }
  }
  async function run() {
    if (!prompt.trim()) { promptRef.current?.focus(); return; }
    const request = { prompt: prompt.trim(), strength, max_tokens: maxTokens, recipe_id: RECIPE_ID, schema_version: 1 };
    const fingerprint = JSON.stringify(request);
    if (!pending.current || pending.current.fingerprint !== fingerprint) pending.current = { fingerprint, key: crypto.randomUUID() };
    setSubmitting(true);
    try {
      const data = await api('/api/comparisons', { method: 'POST', headers: { 'Content-Type': 'application/json', 'Idempotency-Key': pending.current.key }, body: fingerprint });
      pending.current = null; sequenceRef.current = 0; setRecorded(false); setConnectionLost(false);
      setJob(data); setJobId(data.id); sessionStorage.setItem('neuron-dj.active', data.id);
    } catch (e) { notify((e as Error).message); }
    finally { setSubmitting(false); }
  }
  async function stop() {
    if (!job) return;
    try { setJob(await api(`/api/comparisons/${job.id}`, { method: 'DELETE' })); }
    catch (e) { notify((e as Error).message); }
  }
  async function loadModel() {
    try { setRuntime(await api('/api/runtime/load', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: '{}' })); }
    catch (e) { notify((e as Error).message); }
  }
  async function copyLink() {
    try { await navigator.clipboard.writeText(recipeLink(makeRecipe(selected?.name || 'Custom mix'), location.href)); notify('Recipe link copied. It contains settings only.'); }
    catch { notify('Clipboard access is unavailable. Export the recipe as a file instead.'); }
  }

  const runtimeLabel = runtime.state === 'ready' ? 'Model connected' : runtime.state === 'loading' ? 'Model loading' : runtime.state === 'disconnected' ? 'Service offline' : 'Model not connected';
  return <>
    <header className="topbar">
      <a className="brand" href="/" aria-label="Neuron DJ home"><span className="brand-mark"><Icon name="wave" size={23}/></span><span>neuron<span className="brand-dj">dj</span><sup>LAB</sup></span></a>
      <span className="topbar-caption">A personality mixing instrument</span>
      <div className="topbar-actions"><span className="local-tag"><Icon name="cpu" size={14}/> ON YOUR MAC</span>
        <button className="text-button library-button" onClick={() => setPanel('library')}><Icon name="folder"/> Library <span>{recipes.length + savedRuns.length}</span></button>
        <button className="icon-button" onClick={() => setPanel('details')} aria-label="About this experiment"><Icon name="info"/></button></div>
    </header>
    <div className="app-layout">
      <aside className="recipe-rail" aria-label="Recipe bank">
        <div className="rail-title"><span className="eyebrow">01 / RECIPE BANK</span><span className="tiny-number">01</span></div>
        <div className="recipe-card"><div className="recipe-art" aria-hidden="true"><div className="node n1"/><div className="node n2"/><div className="node n3"/><div className="node n4"/><div className="neuron-line l1"/><div className="neuron-line l2"/><div className="neuron-line l3"/><span>13 ↔ 14</span></div>
          <div className="recipe-card-title">The published pair <Icon name="check" size={16}/></div><p>Two neurons. A shift in persona.</p><span className="small-badge">QWEN3.5 · 4B</span></div>
        <div className="preset-label">DOSE VARIATIONS <span>× reference</span></div>
        <div className="preset-list">{presets.map((preset, index) => <button key={preset.name} className={`preset ${strength === preset.strength ? 'selected' : ''}`} onClick={() => setStrength(preset.strength)} aria-pressed={strength === preset.strength}>
          <span className="preset-index">0{index + 1}</span><span className="preset-name">{preset.name}<small>{preset.note}</small></span><span className="preset-value">{preset.strength.toFixed(2)}</span></button>)}</div>
        <button className="save-mix" onClick={() => { setRecipeName(selected ? `My ${selected.name.toLowerCase()} mix` : 'My custom mix'); setPanel('save'); }}><Icon name="plus" size={15}/> Save this mix</button>
        {recipes.length > 0 && <div className="saved-recipes"><span className="eyebrow">YOUR MIXES</span>{recipes.slice(0, 5).map(recipe => <button key={recipe.id} className="saved-recipe" onClick={() => applyRecipe(recipe)}><Icon name="sliders" size={14}/><span>{recipe.name}</span><small>{recipe.strength.toFixed(2)}×</small></button>)}</div>}
        <div className="rail-bottom"><span className="experiment-dot"/><span>AN OPEN EXPERIMENT</span><p>These controls change activations.<br/>Behavior can vary by prompt.</p><button className="text-link" onClick={() => setPanel('details')}>Inside the recipe <Icon name="arrow" size={13}/></button></div>
      </aside>
      <main>
        <section className="workspace-intro"><div><div className="eyebrow"><span className="live-dot"/> MODEL PERSONALITY PLAYGROUND</div><h1>Turn up the other side.</h1><p>One prompt. The original model and your remix, side by side.</p></div><div className="session-tag"><span>SESSION / 001</span><strong>Qwen3.5 <span>4B</span></strong><small>LOCAL · ACTIVATION STEERING</small></div></section>
        <section className="mixer" aria-label="Mix controls"><div className="mixer-heading"><div><span className="eyebrow">02 / MAKE YOUR MIX</span><h2>Steering strength</h2></div><button className="text-link" onClick={() => { setStrength(.5); setMaxTokens(128); }}><Icon name="reset" size={14}/> Reset</button></div>
          <div className="fader-row"><div className="strength-readout">{strength.toFixed(2)}<span>×</span></div><div className="fader-control"><div className="fader-endpoints"><span>Unmodified</span><span>Published dose</span></div><input type="range" min="0" max={runtime.strength_cap} step="0.05" value={strength} onChange={e => setStrength(Number(e.target.value))} aria-label="Steering strength" aria-valuetext={`${strength.toFixed(2)} times the published dose`} style={{ '--fill': `${strength * 100}%` } as React.CSSProperties}/><div className="fader-ticks" aria-hidden="true">{Array.from({ length: 21 }, (_, i) => <i key={i}/>)}</div></div><div className="mix-label"><span className="mix-indicator"/>{selected?.name || 'Custom dose'}<small>Persona pair · v1</small></div></div>
          <div className="mixer-foot"><span><Icon name="info" size={13}/> Strength scales the intervention; personality changes can be nonlinear.</span>{changed && <span className="pending-tag">Applies to next run</span>}</div></section>
        {runtime.state !== 'ready' && <section className="connection-banner" aria-label="Runtime connection"><span className={`connection-symbol ${runtime.state === 'loading' ? 'pulsing' : ''}`}><Icon name="cpu" size={19}/></span><div><strong>{runtime.state === 'loading' ? 'Bringing your model online' : 'Bring your model online'}</strong><p>{runtime.message}</p></div><button className="button secondary" onClick={() => setPanel('setup')}>{runtime.state === 'loading' ? 'View status' : 'Local setup'}<Icon name="arrow" size={15}/></button></section>}
        <div className="comparison-heading"><span className="eyebrow">03 / COMPARE THE SIGNAL</span><div className="comparison-tools">{job && <><button className="text-button" onClick={saveRun} disabled={busy}><Icon name="save" size={14}/> Save run</button><button className="text-button" onClick={() => setPanel('export')} disabled={busy}><Icon name="share" size={14}/> Export</button></>}<button className="text-button" onClick={() => setPanel('details')}><Icon name="sliders" size={14}/> Run details</button></div></div>
        {recorded && <div className="recorded-label"><Icon name="folder" size={14}/> Recorded playback · saved output, no inference running</div>}
        <section className="decks" aria-label="Response comparison">{(['original', 'remix'] as const).map((side, i) => {
          const text = job?.outputs[side] || '';
          const generating = job?.status === `running-${side}`;
          const metrics = job?.metrics[side];
          const sideStatus = generating ? 'Generating' : metrics ? metrics.stop_reason === 'length' ? 'Token limit reached' : metrics.stop_reason === 'stopped' ? 'Partial' : 'Complete' : job?.status === 'stopping' ? 'Stopping' : busy ? 'Waiting' : text ? 'Partial output' : 'Waiting for a prompt';
          return <article className={`deck ${side}`} key={side}><header className="deck-header"><div><span className="deck-letter">{i === 0 ? 'A' : 'B'}</span><h2>{i === 0 ? 'Original' : 'Remix'}</h2><span className="deck-dose">{i === 0 ? '0.00' : (job?.request.strength ?? strength).toFixed(2)}×</span></div><span className="deck-type">{i === 0 ? 'BASELINE' : 'STEERED'}</span></header>
            <div className="deck-content" aria-label={`${side} response`} aria-live="off">{text ? <div className="response-text">{text}{generating && <span className="typing-cursor"/>}</div> : <div className="empty-deck"><span className="empty-icon"><Icon name={i === 0 ? 'wave' : 'sliders'} size={25}/></span><h3>{i === 0 ? 'The original signal' : 'A different expression'}</h3><p>{i === 0 ? 'Unmodified Qwen will answer here.' : 'The same model, with your chosen intervention.'}</p><span className="empty-rule"/></div>}</div>
            <footer className="deck-footer"><span><i className={generating ? 'status-dot generating' : 'status-dot'}/>{sideStatus}</span><span>{metrics ? `${metrics.tokens} tokens · ${metrics.seconds.toFixed(1)}s` : '— tokens'}</span></footer></article>;
        })}</section>
        <div className="run-status" role="status" aria-live="polite">{connectionLost && busy ? 'Connection interrupted. Reconnecting to your existing run…' : job ? `${statusText(job.status)}${job.queue_position ? ` · position ${job.queue_position}` : ''}` : 'Both decks receive the same prompt and generation settings.'}{job?.error && <span className="inline-error">{job.error}</span>}</div>
        <section className="composer"><div className="composer-label"><label htmlFor="prompt">THE SHARED PROMPT</label><span>{prompt.length.toLocaleString()} / 4,000</span></div><textarea ref={promptRef} id="prompt" value={prompt} maxLength={4000} placeholder="Give both sides something to work with…" onChange={e => setPrompt(e.target.value)} onKeyDown={e => { if ((e.metaKey || e.ctrlKey) && e.key === 'Enter' && !busy && runtime.state === 'ready') { e.preventDefault(); run(); } }}/><div className="prompt-chips"><span>Try a prompt</span>{starters.map(text => <button key={text} onClick={() => { setPrompt(text); promptRef.current?.focus(); }}>{text}<Icon name="arrow" size={12}/></button>)}</div><div className="composer-actions"><label className="output-limit">Response length <select value={maxTokens} onChange={e => setMaxTokens(Number(e.target.value))}><option value={96}>Short · 96 tokens</option><option value={128}>Standard · 128 tokens</option><option value={256}>Long · 256 tokens</option></select></label><div className="run-actions">{busy ? <button className="button stop-button" onClick={stop} disabled={job?.status === 'stopping'}><Icon name="stop" size={15}/>{job?.status === 'stopping' ? 'Stopping…' : 'Stop generation'}</button> : <><span className="keyboard-hint">⌘ ↵</span><button className="button primary" onClick={run} disabled={submitting || !prompt.trim() || runtime.state !== 'ready'}><Icon name="play" size={16}/>{submitting ? 'Starting…' : 'Run comparison'}<Icon name="arrow" size={17}/></button></>}</div></div></section>
        <footer className="workspace-footer"><span><span className={`runtime-dot ${runtime.state === 'ready' ? 'connected' : ''}`}/>{runtimeLabel}</span><span>Single-turn · greedy decoding · sequential inference</span><button className="text-link" onClick={() => inputFile.current?.click()}><Icon name="upload" size={13}/> Import recipe or replay</button></footer>
      </main>
    </div>
    <input ref={inputFile} className="visually-hidden" type="file" accept=".json,application/json" aria-label="Import a recipe or replay" onChange={e => { importFile(e.target.files?.[0]); e.target.value = ''; }}/>
    {toast && <div className="toast" role="status"><Icon name="info" size={17}/><span>{toast}</span><button className="icon-button" onClick={() => setToast('')} aria-label="Dismiss notification"><Icon name="close" size={15}/></button></div>}
    {panel === 'setup' && <Modal title="Connect your local model" onClose={() => setPanel(null)}><p className="dialog-intro">The interface is ready. Generation needs the pinned Qwen checkpoint and a local Python runtime.</p><div className={`setup-status ${runtime.state}`}><span className="runtime-dot"/><div><strong>{runtimeLabel}</strong><p>{runtime.message}</p></div></div><div className="setup-steps"><div><span>01</span><div><h3>Install the model packages</h3><p>Use Python 3.12 in this project's virtual environment.</p><code>.venv/bin/python -m pip install -e &quot;.[model]&quot;</code></div></div><div><span>02</span><div><h3>Download the checkpoint once</h3><p>About 9.34 GB. Keep at least 25 GiB free. The cache stays in this project.</p><code>.venv/bin/python scripts/download_model.py</code></div></div><div><span>03</span><div><h3>Load and calibrate</h3><p>The model will be calibrated on ordinary prompts. Local performance and the useful strength range still need a pilot.</p><button className="button primary" disabled={runtime.state === 'loading' || runtime.state === 'ready' || runtime.state === 'disconnected'} onClick={loadModel}><Icon name="cpu"/>{runtime.state === 'loading' ? 'Loading on your Mac…' : runtime.state === 'ready' ? 'Model connected' : 'Load cached model'}</button></div></div></div><p className="dialog-note">Your prompts stay on this Mac. No cloud key is required. Loading never triggers an automatic weight download.</p></Modal>}
    {panel === 'details' && <Modal title="Inside the experiment" onClose={() => setPanel(null)}><p className="dialog-intro">A reversible activation intervention, applied to the same checkpoint. A change in tone alone does not establish a safety jailbreak.</p><dl className="details-list"><div><dt>Model</dt><dd>Qwen3.5-4B</dd></div><div><dt>Mechanism</dt><dd>MLP activation steering</dd></div><div><dt>Published pair</dt><dd>L14 / N8949 +1<br/>L13 / N7956 −1</dd></div><div><dt>Calibration</dt><dd>Residual-normalized, computed locally</dd></div><div><dt>Evidence</dt><dd>Published recipe · local dose pilot pending</dd></div><div><dt>Displayed strength</dt><dd>{(job?.request.strength ?? strength).toFixed(2)}× {job ? '(run snapshot)' : '(next run)'}</dd></div><div><dt>Generation</dt><dd>Greedy · thinking disabled · {job?.request.max_tokens ?? maxTokens} output tokens max</dd></div><div><dt>Runtime</dt><dd>{String(job?.runtime.profile?.device || runtime.profile?.device || 'Not loaded')} / {String(job?.runtime.profile?.dtype || runtime.profile?.dtype || '—')}</dd></div><div><dt>Checkpoint</dt><dd className="revision">{REVISION}</dd></div></dl><a className="source-link" href="https://github.com/shmuelamar/evil-qwen" target="_blank" rel="noreferrer">Read the published reproduction <Icon name="arrow" size={15}/></a></Modal>}
    {panel === 'save' && <Modal title="Save your mix" onClose={() => setPanel(null)}><form onSubmit={saveRecipe}><p className="dialog-intro">Save settings on this browser. Your prompt and responses are not included.</p><label className="field-label" htmlFor="recipe-name">Mix name</label><input id="recipe-name" className="text-input" value={recipeName} onChange={e => setRecipeName(e.target.value)} maxLength={48} required/><div className="recipe-preview"><Icon name="sliders"/><span>The published pair</span><strong>{strength.toFixed(2)}×</strong></div><div className="dialog-actions"><button type="button" className="button secondary" onClick={() => download('neuron-dj-recipe.json', makeRecipe())}><Icon name="share" size={16}/> Export file</button><button className="button primary" type="submit"><Icon name="save" size={16}/> Save mix</button></div></form></Modal>}
    {panel === 'export' && job && <Modal title="Export this comparison" onClose={() => setPanel(null)}><p className="dialog-intro">This replay includes the prompt and both outputs below, plus their generation settings. Review the text before sharing.</p><div className="export-preview"><span className="eyebrow">PROMPT</span><p>{job.request.prompt}</p>{(['original', 'remix'] as const).map(side => <div key={side}><span className="eyebrow">{side.toUpperCase()}</span><p>{job.outputs[side] || '(No output)'}</p></div>)}</div><div className="dialog-actions"><button className="button secondary" onClick={copyLink}>Copy settings-only link</button><button className="button primary" onClick={() => download('neuron-dj-replay.json', replayEnvelope(job))}><Icon name="share" size={16}/> Export replay</button></div></Modal>}
    {panel === 'library' && <Modal title="Your local library" onClose={() => setPanel(null)}><p className="dialog-intro">Stored on this browser. Recipes contain settings; saved comparisons also contain text.</p><div className="library-heading"><h3>Saved mixes <span>{recipes.length}</span></h3><button className="text-link" onClick={() => inputFile.current?.click()}><Icon name="upload" size={14}/> Import</button></div>{!recipes.length && <p className="library-empty">Find a dose you like, then choose Save this mix.</p>}{recipes.map(recipe => <div className="library-row" key={recipe.id}><button onClick={() => { applyRecipe(recipe); setPanel(null); }}><Icon name="sliders"/><span>{recipe.name}<small>{recipe.strength.toFixed(2)}× · {recipe.max_tokens} tokens max</small></span></button><button className="icon-button" aria-label={`Delete ${recipe.name}`} onClick={() => storeRecipes(recipes.filter(r => r.id !== recipe.id))}><Icon name="close" size={15}/></button></div>)}<h3 className="library-section">Saved comparisons <span>{savedRuns.length}</span></h3>{!savedRuns.length && <p className="library-empty">Completed runs stay in memory until you explicitly save them.</p>}{savedRuns.map(value => <div className="library-row" key={value.id}><button onClick={() => viewReplay(value)}><Icon name="folder"/><span>{value.request.prompt.slice(0, 65)}<small>{value.request.strength.toFixed(2)}× · Recorded playback</small></span></button><button className="icon-button" aria-label="Delete saved comparison" onClick={() => { const next = savedRuns.filter(j => j.id !== value.id); try { localStorage.setItem('neuron-dj.runs.v1', JSON.stringify(next.map(replayEnvelope))); setSavedRuns(next); } catch { notify('Could not update browser storage.'); } }}><Icon name="close" size={15}/></button></div>)}{examples.length > 0 && <><h3 className="library-section">Recorded local examples</h3>{examples.map(value => <button className="example-button" key={value.id} onClick={() => viewReplay(value)}>{value.request.prompt}<Icon name="arrow" size={15}/></button>)}</>}</Modal>}
  </>;
}

createRoot(document.getElementById('root')!).render(<App/>);
