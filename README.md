**Neuron DJ**

A local instrument for comparing Qwen3.5-4B with a reversible persona intervention. One prompt, one checkpoint, two response decks. Generation, recipes, and saved comparisons stay on your Mac.

The interface includes a strength fader, dose variations, paired streamed responses, cooperative stopping, local recipes, settings-only links, explicit replay exports, and a setup panel. It uses one model-owning worker and generates Original followed by Remix.

The studio places prompt entry before results, supports focused Original/Remix views, and lets you copy either response. Streaming follows new text until you scroll up; use **Jump to latest** to resume following. Each comparison keeps its original prompt and settings, with a restore action for another run. The last five completed/stopped/failed comparisons received in this tab appear under **This session**; save a run in the Library to keep it after closing the tab.

**Run locally**

Use macOS on Apple silicon, Python 3.12+, and Node.js 22+. The first model download is approximately 9.34 GB; keep at least 25 GiB free. A 16 GB Mac is the intended pilot target, but full-model memory fit and responsiveness are not yet validated.

From this directory:

```sh
python3 scripts/setup.py --download-model
python3 scripts/start.py
```

Open the printed local URL, normally `http://127.0.0.1:8791`, and choose **Local setup → Load cached model**. The first load calibrates the recipe on benign prompts, verifies finite logits, and checks zero-strength/baseline recovery. It does not automatically download weights.

For later launches, use only `python3 scripts/start.py`. To change ports, use `python3 scripts/start.py --port 8792`. Run one server process. Do not launch multiple inference workers or a model hot-reload process.

For an interface-only install, use `python3 scripts/setup.py --ui-only`. You can also open `apps/web/dist/preview.html` directly after a build. The self-contained preview supports recipes and imports but cannot generate responses without the local service.

**What is and is not verified**

The implementation session cannot write `.git`, access external download hosts, or bind localhost ports. React/build dependencies were obtained from existing local package caches. The checkpoint is not cached. Consequently, full-model inference, local calibration, performance, dose/coherence behavior, TCP integration, and visual browser QA are still unverified. The app reports setup/offline states and does not substitute generated mock text.

Offline verification covers the production UI bundle in a DOM test environment, recipe/replay import validation, storage-failure handling, request contracts, origin/host restrictions, queue bounds, idempotency, cancellation lifetime, and stream replay. A separate real-PyTorch tensor check verified signed offsets across batch/prefill/decode shapes and restoration without weight edits. This does not replace a real Qwen pilot.

The implementation and interface review is recorded in [REVIEW.md](REVIEW.md), including fixed defects, regression coverage, and remaining verification limits.

**Model setup in individual steps**

If you prefer to inspect each step:

```sh
python3.12 -m venv .venv
.venv/bin/python -m pip install -e ".[model]"
npm ci
npm run build
.venv/bin/python scripts/download_model.py
python3 scripts/start.py
```

The model/tokenizer revision is pinned to `851bf6e806efd8d0a36b00ddf55e13ccb7b8cd0a`. Files live in `.cache/huggingface`; calibration and optional pilot outputs live in `.neuron-dj`. Both directories are ignored by Git. Browser recipes and explicitly saved comparisons live in that browser's storage for the exact local origin; changing the port creates a different storage origin.

The candidate MPS profile uses FP16/eager attention; CPU uses BF16. Override only when testing a deliberate new profile:

```sh
NEURON_DJ_DEVICE=cpu NEURON_DJ_DTYPE=bfloat16 python3 scripts/start.py
```

A changed runtime profile recalibrates. An incompatible saved calibration profile is rejected. If loading runs out of memory or encounters unsupported MPS operations, preserve the error and measured limits before choosing a lower-memory runtime. No remote inference is configured.

**Run the live pilot**

After the model is available, close any running model service to avoid loading a second copy, then run:

```sh
.venv/bin/python scripts/pilot.py
```

This generates nine paired comparisons from three ordinary prompts at three strengths, writing completed pairs incrementally to `.neuron-dj/pilot.json`. Review coherence, tone, stopping, memory, and timing before calling a strength validated. The UI labels the range experimental. To make genuine generated half-dose examples available in the Library, rerun with `--save-examples`; no fabricated examples are shipped.

The published pair is L14/N8949 +1 and L13/N7956 −1. Strength scales both calibrated offsets. It is not a percentage of a personality trait. The implementation changes activation inputs to `down_proj` within a scope, removes hooks on every exit, and starts each comparison leg with fresh generation state. Tone changes alone do not establish broader safety or capability claims.

**Checks**

```sh
npm run typecheck
npm run build
npm test
python3 -m unittest discover -s tests -v
```

Run the Python suite with `.venv/bin/python` after installing model dependencies to include the real tensor test. Without PyTorch, only that test skips. Test-generated text is confined to test fixtures.

**Structured history**

Git initialization was rejected by the workspace's `.git` write restriction. Milestone snapshots were preserved in `.artifacts/history.fi` with conventional subjects and your configured Git identity. They contain no AI attribution trailers. They are prepared history, not commits already created in this checkout.

From a normal terminal with `.git` writes available:

```sh
python3 scripts/import_history.py
```

The importer initializes an empty repository, imports the milestones, and updates the index without replacing working files. It refuses to overwrite an existing committed history. The `.artifacts` directory is local delivery data; retain it until importing the commits.

**Source map**

- `apps/web`: React/TypeScript instrument and production-bundle DOM tests.
- `services/inference`: loopback HTTP server, contracts, bounded job manager, model adapter, and steering scope.
- `tests`: Python contracts, isolation, queue, HTTP-handler, and tensor checks.
- `scripts`: setup, build, launch, download, pilot, and deferred history tools.
- `NEURON_DJ_PLAN.md`: accepted product plan.
- `EXPERIMENT_PLAN.md`: preserved, separate research plan.

Inspired by the [original neuron explorer](https://github.com/lyramakesmusic/neuron-explorer) and [published persona reproduction](https://github.com/shmuelamar/evil-qwen). Model details are from the [official Qwen checkpoint](https://huggingface.co/Qwen/Qwen3.5-4B). Bundled third-party UI code retains its license notices.
