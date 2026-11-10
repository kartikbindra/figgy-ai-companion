# Activation personalities

Choose **Activation personality** in Activation studio, Companion, or Compare methods. There are 14 presets: the original pair, its hostile neuron alone, and twelve additional personalities from [Hedwig's Qwen personality-neuron study](https://www.hedwigai.com/blog/qwen-personality-neurons). The linked [research implementation](https://gist.github.com/shkr/5e38fedf265feccd733061ecc6a6ad03) supplies the experimental context.

| Preset | Zero-based layer / neuron / sign |
| --- | --- |
| Original published pair | 14 / 8949 / +1; 13 / 7956 / −1 |
| Hostile | 14 / 8949 / +1 |
| Flatterer | 20 / 7450 / −1 |
| Contempt | 17 / 8623 / +1 |
| Poet | 17 / 7426 / +1 |
| Relentlessly upbeat | 5 / 8348 / −1 |
| Suspicious | 5 / 6573 / +1 |
| Condescending | 11 / 6819 / +1 |
| Wistful | 5 / 8940 / −1 |
| Oracle | 5 / 4530 / −1 |
| Bleak | 11 / 2930 / +1 |
| Dismissive | 6 / 6424 / −1 |
| Ornate | 15 / 9125 / +1 |
| Curt | 5 / 7656 / −1 |

These are reported experimental labels. The source used MLX 8-bit, greedy decoding, thinking disabled, and repetition penalty 1.05. This app uses Transformers BF16, its existing six calibration prompts, and its existing greedy generation settings. Results can differ. Curt is specifically flagged by the source as unreliable in BF16; the selector displays that caveat.

Start with a small strength to inspect coherence. Strength zero disables the intervention. Companion defaults to zero, so choosing a neuron preset alone does not change its output. Prompt personality and prompt intensity remain separate controls; Compare methods can isolate prompt-only, activation-only, and combined conditions.

The shared catalog is `services/inference/recipes.json`. Every preset uses the same loaded checkpoint, with temporary hooks on the selected MLP `down_proj` inputs. No extra model copy or fine-tuning is required. All fourteen unique coordinates are calibrated together across eight layers. Coefficients are keyed by both layer and neuron, because different columns in one layer have different norms. A catalog fingerprint invalidates older calibration caches on the next load. Hooks are removed after each generation, including errors and cancellation.

The original pair keeps its ID and remains the default for older conversations and imports. Saved mixes, settings links, comparison replays, chat settings, and experiment legs preserve the chosen preset. Chat and method experiments also freeze its coordinates and catalog fingerprint in provenance. The allowlist prevents imported settings from introducing arbitrary neuron coordinates.

For terminal chat:

```sh
python3 scripts/chat.py --activation-recipe qwen-poet-v1 --strength .25
```

`GET /api/recipes` returns all IDs and metadata. The v1 comparison request uses `recipe_id`; v2 conversation and experiment settings use `activation_recipe`. See [API contracts](../contracts/README.md).

To smoke-test every preset against the already running model:

```sh
.venv/bin/python scripts/pilot_personalities.py
```

This runs Original/Remix comparisons sequentially at strength 0.25 with a 16-token limit and writes actual responses incrementally to `.neuron-dj/personality-pilot.json`. It does not load another model. A short generation check establishes that the path executes; assessing personality quality requires longer outputs, varied prompts, and multiple doses.

Automated verification: 52 Python tests and 19 JavaScript tests pass, plus TypeScript and the production build. Coverage includes per-neuron calibration, every preset's signed tensor offsets and hook cleanup, API selection/provenance, invalid IDs, UI selection, and saved recipe/link identity.

November 10 local check: the real Qwen checkpoint loaded on MPS/BF16, calibrated all fourteen coordinates, and passed finite-logit, zero-strength, and baseline-recovery checks in 207.072 seconds. The subsequent live pilot did not finish its first comparison after five minutes. macOS reported roughly 12 GiB of swap in use, and a process sample showed a Metal command wait. The pilot was stopped and the model process unloaded to relieve pressure. No all-preset generation pass or local personality-quality result is claimed. Runtime measurements remain in the ignored `.neuron-dj/personality-load-status.json`; rerun the pilot with more available memory.
