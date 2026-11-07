import type { Runtime } from './types';

type Props = { runtime: Runtime; device: string; onDeviceChange: (value: string) => void; onLoad: () => void };

export function ModelSetup({ runtime, device, onDeviceChange, onLoad }: Props) {
  const loading = runtime.state === 'loading';
  const ready = runtime.state === 'ready';
  const offline = runtime.state === 'disconnected';
  const label = ready ? 'Model connected' : loading ? 'Model loading' : offline ? 'Service offline' : runtime.state === 'error' ? 'Model loading failed' : 'Ready to load';
  return <>
    <div className={`setup-status ${runtime.state}`} role="status"><span className="runtime-dot"/><div>
      <strong>{label}</strong><p>{runtime.message}</p>
      {loading && <p className="load-progress">{runtime.loading_device?.toUpperCase() || 'Preparing runtime'} · {Math.floor(runtime.load_elapsed_seconds || 0)}s elapsed.
        {runtime.stage_elapsed_seconds != null && ` ${Math.floor(runtime.stage_elapsed_seconds)}s in this step.`} First-time CPU calibration can take several minutes.</p>}
    </div></div>
    <label className="device-choice">Run model on <select value={device} onChange={e => onDeviceChange(e.target.value)} disabled={loading || ready}>
      <option value="auto">Automatic · prefer Apple GPU</option><option value="cpu">CPU · slower recovery option</option><option value="mps">Apple GPU · MPS</option>
    </select></label>
    <button className="button primary" disabled={loading || ready || offline || !runtime.dependencies_available} onClick={onLoad}>
      {loading ? 'Loading on your Mac…' : ready ? 'Model connected' : 'Load cached model'}
    </button>
    <p className="dialog-intro">First load calibrates six prompts and checks baseline recovery. Progress appears above and in your terminal. If GPU loading closes the service, restart it and choose CPU; CPU generation can be very slow.</p>
    <details className="setup-help" open={offline || !runtime.dependencies_available}>
      <summary>Startup and first-time installation</summary>
      <div className="setup-steps">
        <div><span>01</span><div><h3>Start the local instrument</h3><p>Run from the project directory. Keep the terminal open and use the local URL it prints.</p><code>python3 scripts/start.py --open</code><p>For CPU recovery:</p><code>python3 scripts/start.py --cpu --open --load-model</code></div></div>
        <div><span>02</span><div><h3>Install and download once</h3><p>If packages or weights are missing, use the setup command. The checkpoint is about 9.34 GB; keep at least 25 GiB free.</p><code>python3 scripts/setup.py --download-model</code></div></div>
      </div>
    </details>
    <p className="dialog-note">Your prompts stay on this Mac. Loading uses the local cache and does not download weights automatically.</p>
  </>;
}
