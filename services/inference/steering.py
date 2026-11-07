"""Reversible residual-normalized activation intervention; weights are never edited."""
from contextlib import contextmanager
import hashlib
import json
import math

COMPONENTS = ((14, 8949, 1.0), (13, 7956, -1.0))
CALIBRATION_PROMPTS = (
    'Describe a quiet morning in two sentences.',
    'Explain why the sky appears blue in simple language.',
    'Help me organize a small desk.',
    'What is the difference between a map and a photograph?',
    'Suggest a name for a friendly library cat.',
    'Describe how you would plan an ordinary Monday.',
)
METHOD = 'pooled-token-median-layer-output-excluding-position-zero-v1'
PROMPT_HASH = hashlib.sha256(json.dumps(CALIBRATION_PROMPTS).encode()).hexdigest()


@contextmanager
def scoped_steering(layers, units, strength):
    if not math.isfinite(strength) or not 0 <= strength <= 1:
        raise ValueError('Strength must be between zero and one.')
    handles = []
    try:
        if strength:
            for layer, neuron, sign in COMPONENTS:
                delta = float(units[str(layer)]) * sign * strength
                if not math.isfinite(delta):
                    raise ValueError('Invalid calibration coefficient.')

                def hook(module, args, index=neuron, amount=delta):
                    value = args[0].clone()
                    value[..., index] += value.new_tensor(amount)
                    return (value, *args[1:])

                handles.append(layers[layer].mlp.down_proj.register_forward_pre_hook(hook))
        yield
    finally:
        # Attempt every removal even if an earlier handle fails.
        errors = []
        for handle in reversed(handles):
            try:
                handle.remove()
            except Exception as exc:
                errors.append(exc)
        if errors:
            raise RuntimeError('Steering cleanup failed; reload the runtime before another run.') from errors[0]


def calibrate(runtime):
    import torch
    layers = runtime.model.model.language_model.layers
    values = {str(layer): [] for layer, _, _ in COMPONENTS}
    handles = []
    try:
        for layer in values:
            def capture(module, args, output, key=layer):
                hidden = output[0] if isinstance(output, tuple) else output
                norms = hidden.detach().float().norm(dim=-1)
                values[key].append(norms[:, 1:].flatten().cpu())
            handles.append(layers[int(layer)].register_forward_hook(capture))
        with torch.inference_mode():
            for index, prompt in enumerate(CALIBRATION_PROMPTS, 1):
                runtime._state('loading', f'Calibrating persona recipe: prompt {index}/{len(CALIBRATION_PROMPTS)}…')
                if hasattr(runtime.model.model, 'rope_deltas'):
                    runtime.model.model.rope_deltas = None
                # Calibration uses decoder activations only. Avoid the large vocabulary
                # projection at every input token; the base model runs identical layers.
                runtime.model.model(**runtime.inputs(prompt), use_cache=False)
    finally:
        for handle in handles:
            handle.remove()
        if hasattr(runtime.model.model, 'rope_deltas'):
            runtime.model.model.rope_deltas = None
    units, medians, columns = {}, {}, {}
    for layer, neuron, _ in COMPONENTS:
        median = float(torch.cat(values[str(layer)]).median())
        norm = float(layers[layer].mlp.down_proj.weight[:, neuron].detach().float().norm())
        if not math.isfinite(median) or not math.isfinite(norm) or median <= 0 or norm <= 0:
            raise ValueError('Calibration produced an invalid residual or column norm.')
        units[str(layer)] = median / norm
        medians[str(layer)], columns[str(layer)] = median, norm
    return {'method': METHOD, 'prompt_hash': PROMPT_HASH, 'profile_hash': runtime.profile['hash'],
            'units': units, 'residual_medians': medians, 'column_norms': columns}
