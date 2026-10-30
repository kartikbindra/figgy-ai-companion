export const REVISION = '851bf6e806efd8d0a36b00ddf55e13ccb7b8cd0a';
export const RECIPE_ID = 'qwen-persona-pair-v1';
export const terminal = (status) => ['complete', 'stopped', 'failed'].includes(status);
export const statusText = (status) => ({ queued: 'In the queue', 'running-original': 'Generating original',
  'running-remix': 'Generating remix', stopping: 'Stopping…', complete: 'Comparison complete',
  stopped: 'Stopped · partial output', failed: 'Run interrupted' }[status] || 'Ready for a prompt');

export function validateRecipe(value) {
  if (!value || value.kind !== 'neuron-dj-recipe' || value.schema_version !== 1 ||
      value.recipe_id !== RECIPE_ID || value.model_revision !== REVISION ||
      typeof value.name !== 'string' || !value.name.trim() || value.name.length > 48 ||
      typeof value.strength !== 'number' || !Number.isFinite(value.strength) || value.strength < 0 || value.strength > 1 ||
      !Number.isInteger(value.max_tokens) || value.max_tokens < 16 || value.max_tokens > 256 ||
      !(value.profile_hash === null || typeof value.profile_hash === 'string' && /^[a-f0-9]{64}$/.test(value.profile_hash))) {
    throw new Error('This recipe is incompatible or has invalid settings. Use a Neuron DJ v1 recipe for Qwen3.5-4B.');
  }
  return { kind: 'neuron-dj-recipe', schema_version: 1, id: typeof value.id === 'string' ? value.id.slice(0, 80) : crypto.randomUUID(),
    name: value.name.trim(), recipe_id: RECIPE_ID, model_revision: REVISION,
    strength: value.strength, max_tokens: value.max_tokens, profile_hash: value.profile_hash };
}

export function validateReplay(value) {
  const job = value?.comparison;
  if (value?.kind !== 'neuron-dj-replay' || value.schema_version !== 1 || value.recorded !== true || !job ||
      !terminal(job.status) || typeof job.request?.prompt !== 'string' || job.request.prompt.length > 4000 ||
      typeof job.outputs?.original !== 'string' || typeof job.outputs?.remix !== 'string' ||
      job.outputs.original.length > 20000 || job.outputs.remix.length > 20000 ||
      typeof job.id !== 'string' || !job.runtime || job.runtime.model_revision !== REVISION) {
    throw new Error('This file is not a compatible Neuron DJ replay.');
  }
  validateRecipe({ kind: 'neuron-dj-recipe', schema_version: 1, id: 'replay', name: 'Replay',
    recipe_id: job.request.recipe_id, model_revision: job.runtime.model_revision,
    strength: job.request.strength, max_tokens: job.request.max_tokens, profile_hash: null });
  // Only the known renderable fields survive import. No imported metrics or runtime instructions execute.
  return { ...job, id: job.id.slice(0, 80), sequence: 0,
    created_at: typeof job.created_at === 'string' ? job.created_at.slice(0, 64) : '', metrics: {},
    runtime: { model_id: 'Qwen/Qwen3.5-4B', model_revision: REVISION, profile: null },
    error: typeof job.error === 'string' ? job.error.slice(0, 500) : null, queue_position: null };
}

export function recipeLink(recipe, base) {
  const bytes = new TextEncoder().encode(JSON.stringify(validateRecipe(recipe)));
  const encoded = btoa(String.fromCharCode(...bytes));
  const url = new URL(base);
  url.hash = 'recipe=' + encodeURIComponent(encoded);
  return url.toString();
}

export function recipeFromHash(hash) {
  if (!hash.startsWith('#recipe=')) return null;
  if (hash.length > 4000) throw new Error('This recipe link is too large.');
  try {
    const decoded = atob(decodeURIComponent(hash.slice(8)));
    return validateRecipe(JSON.parse(new TextDecoder().decode(Uint8Array.from(decoded, c => c.charCodeAt(0)))));
  } catch { throw new Error('This recipe link is invalid or incompatible.'); }
}

export function readStored(key, validate, limit = 12) {
  try {
    const value = JSON.parse(localStorage.getItem(key) || '[]');
    return Array.isArray(value) ? value.slice(0, limit).map(validate) : [];
  } catch { return []; }
}
