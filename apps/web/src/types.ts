export type Runtime = {
  state: 'not_loaded' | 'loading' | 'ready' | 'error' | 'disconnected';
  message: string; dependencies_available: boolean; model_id: string; model_revision: string;
  profile: null | Record<string, string | boolean>; strength_cap: number;
  evidence: string; load_seconds: number | null;
  load_elapsed_seconds?: number | null; stage_elapsed_seconds?: number | null; loading_device?: string | null;
};
export type Request = { prompt: string; strength: number; max_tokens: number; recipe_id: string; schema_version: 1 };
export type Job = {
  id: string; schema_version: 1; sequence: number; created_at: string;
  status: 'queued' | 'running-original' | 'running-remix' | 'stopping' | 'complete' | 'stopped' | 'failed';
  request: Request; runtime: Runtime; outputs: { original: string; remix: string };
  metrics: Partial<Record<'original' | 'remix', { tokens: number; seconds: number; stop_reason: string }>>;
  error: string | null; queue_position: number | null;
};
export type Recipe = {
  kind: 'neuron-dj-recipe'; schema_version: 1; id: string; name: string;
  recipe_id: string; model_revision: string; strength: number; max_tokens: number; profile_hash: string | null;
};
