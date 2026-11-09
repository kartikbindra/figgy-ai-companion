**Neuron DJ**

A local companion and experiment studio built from Neuron DJ and Figgy. Chat with persistent conversations, choose or blend five prompt personalities, inspect remembered facts, and compare personality prompts with reversible Qwen activation steering.

The app now has four workspaces:

- **Companion:** streamed chat, conversation-specific personality settings, optional activation strength, and selective local memory. Prompt intensity and activation strength are independent controls. Activation defaults to zero.
- **Activation studio:** the original paired Original/Remix workflow, with existing recipes and saved comparisons preserved.
- **Compare methods:** baseline, prompt only, activation only, and combined conditions. Select two to four conditions and a strength; all run sequentially with matched greedy decoding. Memory and history are excluded from these experiments.
- **Memory:** inspect and delete explicit facts learned from completed chat turns. Memory is local to this owner's profile; this is a single-user application.

Start the unified app with the existing command:

```sh
python3 scripts/start.py --open
```

Use **Local setup** to load the cached model, then open **Companion** or **Compare methods**. Chat and experiments share one model-owning worker, bounded queue, replayable stream, and cooperative stopping. Conversations, settings, and partial-turn checkpoints are stored in `.neuron-dj/companion.sqlite3`; unfinished turns are marked interrupted after a restart and excluded from future context. Input stays within the current 768-token Qwen budget by retaining the latest complete history pairs that fit. Overlong mandatory instructions/messages produce an explicit error.

For the terminal client, start the service first, then run `python3 scripts/chat.py`. Use `--conversation ID` to resume a session and `--persona existentialist` to select a personality.

The unified backend requires FastAPI and Uvicorn, installed by the normal setup command. An existing checkout can update only the application dependencies with `.venv/bin/python -m pip install -e .`; the model cache is reused. Model packages remain lazy, and voice packages are not needed for text use. The new setup and API use `services.api`; `services.inference.server` remains a legacy implementation retained for compatibility tests.

Optional Ollama launch, using an explicitly installed local model:

```sh
NEURON_DJ_PROVIDER=ollama LLM_MODEL=your-installed-model python3 scripts/start.py --open --load-model
```

Ollama supports companion chat and baseline/prompt comparisons. The app disables activation controls for that provider, records its installed model digest and details, and rejects unsupported activation requests. Its context accounting is a conservative UTF-8 byte estimate, labeled in the runtime profile; the Qwen provider uses its actual tokenizer. Provider selection is per process launch. Keep only one model-serving stack active when measuring memory or latency.

The cloned `figgy-ai-companion` directory is preserved as upstream reference at revision `376ccad`; the unified launcher does not start its backend or dashboard. Its voice/device APIs, ESP32 firmware work, and advanced memory remain follow-up work. This first integration learns a small set of explicit name, interest, and location facts; it does not implement semantic search or episodic summarization. Existing standalone Figgy databases are not automatically imported.

Implementation details, current verification, and remaining gates are in [docs/UNIFIED_IMPLEMENTATION.md](docs/UNIFIED_IMPLEMENTATION.md); the original [integration plan](docs/UNIFICATION_PLAN.md) remains available.

The following sections retain the original activation-studio runtime guidance and prior measurements.

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

For later launches, double-click **Neuron DJ.command** to open the app and load the cached model, or use `python3 scripts/start.py --open --load-model`. The launcher rebuilds stale UI assets before starting. To change ports, use `python3 scripts/start.py --port 8792`. Run one server process. Do not launch multiple inference workers or a model hot-reload process.

`npm start` also uses this launcher and selects `.venv/bin/python` automatically. Keep the terminal running while using the app.

**If the page opens but the model will not load**

1. Open the HTTP URL printed by the launcher, normally `http://127.0.0.1:8791`. The `file://` preview cannot connect to the inference service.
2. Use `python3 scripts/start.py` or `npm start`. Running `python3 -m services.inference.server` directly uses whichever Python is on your shell's path. On this machine that is Python 3.14 without the model packages; the installed packages are in the project's Python 3.12 `.venv`.
3. Choose **Local setup → Load cached model** and wait for **Model connected**. Loading includes calibration and recovery checks before generation is enabled. Both checkpoint shards are already cached in this checkout, so no repeat download is needed.
4. The setup panel now shows calibration prompt counts, recovery-check steps, elapsed time, and the actual load error. Choose **CPU** there if GPU loading fails. If the process exits, restart with `python3 scripts/start.py --cpu --open --load-model`. CPU generation can be very slow. If it still fails, copy the exact message from the setup panel. Check the runtime from the project environment with `.venv/bin/python -c "import torch; print(torch.__version__); print('MPS available:', torch.backends.mps.is_available())"`. For a direct loading diagnostic, stop the server first, then run `.venv/bin/python -m services.inference.runtime` so only one process owns the model.

If the process exits near `Loading weights: 0%` followed by a leaked-semaphore warning, check the macOS Python crash report in `~/Library/Logs/DiagnosticReports`. The November 1 crash in this checkout was `SIGSEGV` in PyTorch's MPS shader cache during concurrent weight conversion. The runtime now forces sequential weight loading on MPS using `HF_DEACTIVATE_ASYNC_LOAD=1`, the [documented Transformers switch](https://github.com/huggingface/transformers/blob/main/docs/source/en/reference/environment_variables.md). Restart the service to apply the change. The semaphore warning is cleanup after the native crash; reinstalling or downloading the checkpoint again does not address that failure.

This Mac has 16 GiB of unified memory. During troubleshooting only about 3 GiB was available with other applications open. Close memory-heavy applications before loading the full checkpoint. The restricted command environment used for troubleshooting could not bind localhost ports, and PyTorch reported MPS unavailable in that process; start the service and check MPS in your regular macOS terminal. On November 7, CPU loading, calibration, and all recovery checks completed in 217.124 seconds. Both Original and 0.25× Remix then generated 16 real tokens (298.976 and 297.146 seconds respectively). CPU is a slow recovery option on this session, not the intended interactive experience.

For an interface-only install, use `python3 scripts/setup.py --ui-only`. You can also open `apps/web/dist/preview.html` directly after a build. The self-contained preview supports recipes and imports but cannot generate responses without the local service.

**What is and is not verified**

The project environment and both pinned checkpoint shards are installed and cached in this checkout. TypeScript, production build, 15 JavaScript tests, and 33 Python tests pass. CPU loading, calibration, finite logits, baseline recovery, and a short Original/Remix generation completed with the real checkpoint. Native Chrome rendered the file preview and setup dialog. The command environment cannot bind localhost ports and reports MPS unavailable; GPU execution and live browser/API integration still need a regular-terminal check. These short outputs do not validate persona quality or production performance. No simulated responses are shipped.

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

The original milestone history and unified-project progress are committed, with Git metadata in the standard root `.git` directory. The integration branch is `feat/unified-companion-studio`, and `origin` is `https://github.com/kartikbindra/figgy-ai-companion`. Its history includes both the earlier Neuron DJ milestones and Figgy's upstream `main`. The cloned Figgy source is registered as an upstream-reference submodule; the unified application's runtime code lives in the root project.

Normal Git commands now work from this directory:

```sh
git status
git log --oneline
```

The earlier sandbox restriction was resolved after full access was granted. `scripts/import_history.py` remains available for restoring older deliveries whose Git metadata or milestone stream is still under `.artifacts`; it refuses to replace an existing root repository.

**Source map**

- `apps/web`: React/TypeScript instrument and production-bundle DOM tests.
- `services/inference`: loopback HTTP server, contracts, bounded job manager, model adapter, and steering scope.
- `tests`: Python contracts, isolation, queue, HTTP-handler, and tensor checks.
- `scripts`: setup, build, launch, download, pilot, and deferred history tools.
- `NEURON_DJ_PLAN.md`: accepted product plan.
- `EXPERIMENT_PLAN.md`: preserved, separate research plan.

Inspired by the [original neuron explorer](https://github.com/lyramakesmusic/neuron-explorer) and [published persona reproduction](https://github.com/shmuelamar/evil-qwen). Model details are from the [official Qwen checkpoint](https://huggingface.co/Qwen/Qwen3.5-4B). Bundled third-party UI code retains its license notices.
