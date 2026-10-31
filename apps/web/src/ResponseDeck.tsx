import { useEffect, useRef, useState } from 'react';
import type { Job } from './types';

type Props = {
  side: 'original' | 'remix'; job: Job | null; recorded: boolean;
  busy: boolean; strength: number; hidden: boolean; onCopy: () => void;
};

export function ResponseDeck({ side, job, recorded, busy, strength, hidden, onCopy }: Props) {
  const viewport = useRef<HTMLDivElement>(null);
  const follows = useRef(true);
  const [showLatest, setShowLatest] = useState(false);
  const text = job?.outputs[side] || '';
  const metrics = job?.metrics[side];
  const generating = !recorded && job?.status === `running-${side}`;
  const original = side === 'original';
  useEffect(() => { follows.current = true; setShowLatest(false); }, [job?.id]);
  useEffect(() => {
    if (hidden || !viewport.current) return;
    if (follows.current) viewport.current.scrollTop = viewport.current.scrollHeight;
    else setShowLatest(true);
  }, [text, hidden]);
  const status = recorded && text ? 'Recorded output' : generating ? 'Generating' :
    metrics ? metrics.stop_reason === 'length' ? 'Token limit reached' : metrics.stop_reason === 'stopped' ? 'Partial output' : 'Complete' :
    job?.status === 'stopping' ? 'Stopping' : busy ? 'Waiting its turn' : text ? 'Partial output' : 'Ready for a prompt';
  function jump() {
    follows.current = true;
    if (viewport.current) viewport.current.scrollTop = viewport.current.scrollHeight;
    setShowLatest(false);
  }
  return <article className={`deck ${side}`} hidden={hidden}>
    <header className="deck-header">
      <div><span className="deck-letter">{original ? 'A' : 'B'}</span><h2>{original ? 'Original' : 'Remix'}</h2>
        <span className="deck-dose">{original ? '0.00' : (job?.request.strength ?? strength).toFixed(2)}×</span></div>
      <button className="deck-copy" onClick={onCopy} disabled={!text} aria-label={`Copy ${side} response`}>Copy</button>
    </header>
    <div ref={viewport} className="deck-content" tabIndex={0} role="region" aria-label={`${side} response`} aria-live="off"
      onScroll={() => { const el = viewport.current; if (el) { follows.current = el.scrollHeight - el.scrollTop - el.clientHeight < 48; if (follows.current) setShowLatest(false); } }}>
      {text ? <div className="response-text">{text}{generating && <span className="typing-cursor"/>}</div> :
        <div className="empty-deck"><span className={`signal-glyph ${generating ? 'active' : ''}`} aria-hidden="true">{Array.from({ length: 7 }, (_, i) => <i key={i}/>)}</span>
          <h3>{generating ? 'Finding the words…' : original ? 'The familiar voice.' : 'The other side.'}</h3>
          <p>{busy && !generating ? original ? 'Your comparison is waiting for the model.' : 'This deck starts after the original finishes.' : original ? 'Qwen, exactly as it comes. Your baseline for every comparison.' : 'The same prompt with your chosen persona dose. See what changes.'}</p>
          <span className="deck-type">{original ? 'UNMODIFIED MODEL' : 'ACTIVATION STEERING'}</span>
        </div>}
    </div>
    {showLatest && <button className="jump-latest" onClick={jump}>Jump to latest ↓</button>}
    <footer className="deck-footer"><span><i className={`status-dot ${generating ? 'generating' : ''}`}/>{status}</span>
      <span>{metrics ? `${metrics.tokens} tokens · ${metrics.seconds.toFixed(1)}s` : '— tokens'}</span></footer>
  </article>;
}
