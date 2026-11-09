# Unified implementation — 2026-11-10

The first text integration is implemented. `scripts/start.py` now launches one FastAPI application serving the existing React UI and the new companion/method workspaces. `services/inference/server.py` is retained as legacy reference and regression coverage, not as the normal entry point.

## Delivered

- Reused Neuron DJ's pinned Qwen runtime, reversible hooks, calibration, bounded queue, cancellation, deadlines, and replay snapshots. The worker accepts both original v1 comparisons and immutable v2 structured-message jobs. Multi-condition runs retain exclusive model access across all legs.
- Ported Figgy's five profiles and mood rules into `services/personality`, with validated, conversation-scoped configuration and a compact versioned prompt renderer. Fusion weights are normalized; unknown, negative, nonfinite, and boolean values are rejected. Each run retains settings, mood decision, prompt messages, and runtime provenance.
- Added SQLite conversations, persistent defaults, durable idempotency for chat, one pending turn per conversation, scoped explicit-fact memory, and short transactions outside generation. Partial output checkpoints are written at most once per second; a crash can lose up to the most recent checkpoint interval. Shutdown waits for generation/hook cleanup. Pending turns become interrupted on restart; stopped/failed/interrupted turns do not enter normal history or learn memory.
- Added token-budgeted structured history and memory. Actual cached Qwen tokenizer checks found 84–91 tokens for the five individual compact personas and 246 tokens for a five-persona blend with an exhausted-user prompt. These are measured examples, not universal prompt sizes; each submitted request is budgeted independently.
- Added baseline, prompt-only, activation-only, and combined experiments. They share a checkpoint and greedy decoding; history and memory are excluded and experiments never learn facts. Experiment records can be explicitly exported. Old v1 recipes, replay imports, browser storage keys, and comparison routes are preserved.
- Added an optional local Ollama adapter with model/digest probing, structured messages, bounded greedy output, and explicit rejection of activation steering. The configured checkpoint is a different experimental variable from the methodology. Incomplete provider streams are marked failed with partial output preserved.
- Added one React navigation surface and a dependency-free terminal client at `scripts/chat.py`.

## Deliberate implementation choices

Use the standard-library SQLite driver for the first version rather than SQLAlchemy/aiosqlite. Transactions are small and serialized, no connection is held during generation, and synchronous API operations run in FastAPI's thread pool. This keeps the storage boundary testable without ORM dependencies. The database schema is versioned at 1 and refuses newer schema versions.

Use a single configured provider per launch and one local owner profile. Semantic facts belong to that profile; recent conversation turns are isolated by conversation ID. No shared mutable persona singleton remains in the unified path. This is not a multi-account service.

Port persona descriptions into a compact prompt instead of blindly appending the full Figgy identity, profile, history, and mood text. The initial Qwen context cap remains 768 tokens. Oldest history pairs are dropped as needed; required user input and instructions are never silently truncated. No separate model or neural direction is claimed for each persona.

FastAPI is the new required HTTP dependency; Torch/Transformers remain optional and lazy. Network installation was unavailable in this command environment; application/test dependencies were installed from existing local wheel caches. The tested environment includes FastAPI 0.141.1, Uvicorn 0.52.1, and HTTPX 0.28.1.

## Verification

Final checks in this implementation pass: **46 Python tests passed**, **17 JavaScript tests passed**, TypeScript passed, and the production build passed. An isolated startup check served the UI, runtime, health, persona, conversation, and memory routes without importing Torch or Transformers. A direct socket probe confirmed this command environment rejects loopback port binding with `PermissionError: Operation not permitted`; ASGI verification does not establish the live TCP/browser path.

The Python suite exercises the actual ASGI routes, SQLite files, scheduler threads, and event generator using a test-only runtime. It covers durable retry/conflict behavior, frozen settings, conversation reservations through cancellation, completed-turn memory, budget rejection without reservations, provider capabilities, four-condition execution, HTTP origin/host/body/path restrictions, v1 contracts, partial-output recovery, and subscription cleanup. Existing tensor and tiny real-Qwen checks remain part of the suite.

The unified scheduler allows up to one hour per job so four slow CPU legs can finish; the existing bounded queue, 45-second orphan timeout, and explicit stopping remain active. This is an execution limit, not a latency target.

Production-bundle DOM tests cover the original studio plus chat submission, stable streams across workspace switches, stopping, method requests, and safe rendering of stored memory text. TypeScript and production build are required checks. Test output fixtures exist only in tests.

Native browser inspection could not run because the browser access host was unavailable. No new full-checkpoint generation, live Ollama session, or interactive GPU-performance claim is established by these integration tests. Follow the real-model pilot before judging persona quality, latency, or a useful dose range. Prior CPU timings in README.md remain prior observations.

## Remaining work

- Run the unified text flows with the full checkpoint in a normal terminal and browser, including MPS memory/latency and stop/reconnect behavior. A reproducible direct runtime pilot is available as `scripts/pilot_unified.py`; stop any other model-owning service before using it.
- Add episodic checkpoints/summaries, broader explicit fact types, conversation deletion, and a migration/import workflow for any existing standalone Figgy database. The first release only extracts a few explicit facts from the latest successful user turn and does not reprocess old history after a memory deletion.
- Add v2 recipe authoring/import and persistent experiment-library UX beyond explicit JSON recording exports; existing v1 imports retain their original meaning.
- Port optional voice/device APIs behind extras after text validation. End-to-end streaming audio, interruption, ESP32 firmware, remote access, and adapter training are not implemented by this merge.

The upstream Figgy repository and nested Git history remain intact and are registered as an upstream-reference submodule. Source provenance is `376ccad` for copied profiles and mood rules. At the user's request, the earlier milestone stream was imported into a real repository under `.artifacts/git`, and integration progress is committed on `main`. Root `.git` creation remains blocked by this workspace; `python3 scripts/import_history.py` in a regular terminal promotes the saved metadata without replacing working files.
