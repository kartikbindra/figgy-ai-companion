**Implementation status**

November 10: the first unified Figgy/Neuron DJ text integration is implemented. The launcher now uses `services.api`, with companion chat, memory, matched method comparisons, and an optional Ollama provider sharing the scheduler. See [UNIFIED_IMPLEMENTATION.md](UNIFIED_IMPLEMENTATION.md) for current scope and verification. The notes below describe the original activation-studio delivery.

The accepted product plan is `NEURON_DJ_PLAN.md`. Local execution is the delivery target.

The execution sandbox currently rejects `.git` writes, external DNS/network access, and localhost port binding. Python 3.12 is available. React and build tools were obtained from existing local caches. The Qwen3.5-4B checkpoint and model packages are now cached. Real CPU calibration, recovery checks, and short paired generation passed on November 7; see docs/RUNTIME.md for measurements. GPU execution and full app integration are still unverified.

Milestones are retained as a Git fast-import stream in `.artifacts/history.fi`, with the user's configured author identity and conventional commit subjects. When `.git` writes are available, run `python3 scripts/import_history.py` from a normal terminal to create those commits. The importer refuses to replace existing history. No attribution trailers are added.

The web app must show an honest setup state until a real model is available. Fixtures belong only to tests. No invented example is presented as a model recording.

Implemented: static React/TypeScript UI, setup panel, paired response decks, pending next-run controls, local recipes, settings-only links, explicit comparison exports, validated imports, local HTTP/API service, one model-owning worker, immutable paired jobs, bounded queue/replay, idempotency, acknowledged stopping, orphan/deadline cancellation, pinned model loading, profile-bound calibration, and scoped activation hooks.

The HTTP server uses Python's standard library so setup/status and the UI do not require installing model packages. This is an intentional reduction in dependencies from the candidate architecture. The DOM test environment exercises the production bundle without opening a browser or network socket. It does not verify visual layout, native dialog behavior, or real SSE transport.

GPU execution and the live browser/API path remain outstanding gates. The runtime refuses to become ready if finite-logit or baseline-recovery smoke checks fail. The separate pilot command generates actual records but leaves dose/coherence judgments for review. No public deployment was attempted.
