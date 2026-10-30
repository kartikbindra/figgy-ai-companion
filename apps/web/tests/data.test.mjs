import { test } from 'node:test';
import assert from 'node:assert/strict';
import { REVISION, RECIPE_ID, validateRecipe, validateReplay, recipeLink, recipeFromHash } from '../src/data.mjs';

const recipe = { kind: 'neuron-dj-recipe', schema_version: 1, id: 'test', name: '小さな mix 🎛️',
  recipe_id: RECIPE_ID, model_revision: REVISION, strength: .5, max_tokens: 128, profile_hash: null };

test('recipe links preserve Unicode and exclude prompts/responses', () => {
  const link = recipeLink({ ...recipe, prompt: 'private input', outputs: 'private response' }, 'http://127.0.0.1:8791/');
  const loaded = recipeFromHash(new URL(link).hash);
  assert.equal(loaded.name, recipe.name);
  assert.equal(loaded.strength, .5);
  assert.equal('prompt' in loaded, false);
  assert.equal('outputs' in loaded, false);
});
test('invalid numerical settings and incompatible checkpoints are rejected', () => {
  for (const patch of [{ strength: NaN }, { strength: 1.1 }, { max_tokens: 3 },
    { max_tokens: 128.2 }, { model_revision: 'main' }, { profile_hash: 'untrusted' }]) {
    assert.throws(() => validateRecipe({ ...recipe, ...patch }));
  }
});
test('imported recipes discard executable or unsupported fields', () => {
  const value = validateRecipe({ ...recipe, module_path: '/tmp/code.py', units: { 14: 9999 } });
  assert.equal('module_path' in value, false);
  assert.equal('units' in value, false);
});
test('invalid and oversized link payloads fail safely', () => {
  assert.throws(() => recipeFromHash('#recipe=%bad'));
  assert.throws(() => recipeFromHash('#recipe=' + 'x'.repeat(5000)));
  assert.equal(recipeFromHash('#unrelated'), null);
});
test('replay validation refuses active jobs and object-valued outputs', () => {
  const base = { kind: 'neuron-dj-replay', schema_version: 1, recorded: true,
    comparison: { id: 'test', status: 'complete', request: { prompt: 'test-only', ...recipe },
      outputs: { original: 'test-only', remix: 'test-only' }, runtime: { model_revision: REVISION } } };
  assert.equal(validateReplay(base).outputs.original, 'test-only');
  assert.throws(() => validateReplay({ ...base, comparison: { ...base.comparison, status: 'running-remix' } }));
  assert.throws(() => validateReplay({ ...base, comparison: { ...base.comparison, outputs: { original: {}, remix: '' } } }));
});
