# Unified companion and experiment studio — implementation plan

Date: 2026-11-10. Status: proposed implementation, following source review; no application changes made.

Implementation began after this planning pass. See [UNIFIED_IMPLEMENTATION.md](UNIFIED_IMPLEMENTATION.md) for the delivered text integration, deliberate changes to this proposal, verification results, and remaining gates.

The user selected **companion chat plus an experiment studio**. Build one application with a shared inference layer, personality engine, conversation store, and job lifecycle. Keep Neuron DJ as the studio experience and bring Figgy's conversational features into the same React application. Use the existing Mac and pinned Qwen checkpoint for the first integration.

## 1. What the two projects actually implement

| Area | Existing Neuron DJ | Cloned Figgy |
| --- | --- | --- |
| Personality mechanism | Calibrated activation offsets at L14/N8949 (+) and L13/N7956 (−), installed before `down_proj` and removed after generation | Core identity + five persona prompts, textual fusion percentages, intensity instructions, keyword-based mood adjustments |
| Model | Pinned `Qwen/Qwen3.5-4B`, revision `851bf6e806efd8d0a36b00ddf55e13ccb7b8cd0a`, Transformers/PyTorch | Ollama model name defaults to `huihui_ai/qwen3-abliterated`; exact installed model/digest is not established by the source |
| Inference | Synchronous callback streaming, greedy decoding, 768 input tokens, 16–256 output tokens, CPU/MPS | Async HTTP streaming, temperature 0.8 by default; actual payload hard-codes 2,048 context and 120 output tokens despite a 4,096 context setting |
| Interaction | One prompt, Original then Remix, fresh state per leg | Conversation history, persona switching, memory injection |
| Execution | Single worker, bounded queue, idempotency, replayable SSE snapshots, cancellation/deadline/orphan handling | Requests directly call the provider; no equivalent shared scheduler or replay lifecycle |
| Persistence | Browser recipes and explicitly saved comparisons; local calibration/model cache | SQLite conversations, messages, global memories, device status |
| Application | React/TypeScript and standard-library loopback HTTP server | FastAPI backend, standalone HTML dashboard, CLI |
| Additional features | Setup diagnostics, export/import, runtime provenance | Voice endpoints and device command/status APIs; no ESP32 firmware in this checkout |

The existing implementation is activation steering: it does **not** edit model weights. Figgy's fusion weights are prompt instructions: they do **not** mix neural weights or adapters. Figgy selects a separately modified checkpoint but contains no checkpoint-ablation implementation. These are separate mechanisms and must be represented separately in configuration and results.

The Figgy brief describes future per-personality adapters, hardware, and Windows/RTX 3050 deployment. Those are product aspirations, not implemented capabilities of this clone. One published neuron pair does not establish five independently controllable neural personas.

Primary source map:

- [Runtime](../services/inference/runtime.py), [steering](../services/inference/steering.py), [jobs](../services/inference/jobs.py), [HTTP server](../services/inference/server.py).
- [Figgy orchestration](../figgy-ai-companion/backend/app/llm/orchestrator.py), [Ollama adapter](../figgy-ai-companion/backend/app/llm/ollama.py).
- [Personality manager](../figgy-ai-companion/backend/app/personality/manager.py), [fusion](../figgy-ai-companion/backend/app/personality/fusion.py), [profiles](../figgy-ai-companion/backend/app/personality/profiles.py).
- [Memory retrieval](../figgy-ai-companion/backend/app/memory/retrieval.py), [extraction/compaction](../figgy-ai-companion/backend/app/memory/summarizer.py), [database models](../figgy-ai-companion/backend/app/database/models.py).
- Preserve [the existing product plan](../NEURON_DJ_PLAN.md) and [the separate research plan](../EXPERIMENT_PLAN.md). This integration expands product scope; it does not implement the separate refusal-direction research study.

## 2. Product behavior and methodology

### Companion

Create/resume a conversation, select a persona or normalized fusion, adjust prompt intensity, and send streamed turns. Personality changes affect subsequent turns without clearing history. Memory has a visible on/off setting and an inspect/delete view.

Default to Figgy's dark comedian prompt with activation strength **zero**. Offer activation steering as a separate experimental control. Show the provider and model, and retain the exact settings used for each turn. Separate prompt intensity, fusion proportions, and activation strength; never imply they have equivalent units.

### Studio

Support four explicitly labeled conditions on the **same pinned Qwen checkpoint**:

| Condition | Persona prompt | Activation steering |
| --- | --- | --- |
| Baseline | Off, including Figgy core identity/mood | Off |
| Prompt only | On | Off |
| Activation only | Off | On |
| Combined | On | On |

Default to a two-condition comparison and offer a sequential four-condition sweep. Preserve the existing Original/Remix comparison as the baseline-versus-activation preset. Four conditions cost four generations; they do not run concurrently.

Freeze the user input, selected history/memories, persona version, rendered messages, mood decision, recipe, strength, model revision/profile, and decoding settings at submission. Hold history/memory constant across conditions, with both disabled by default in the studio. Studio runs never extract new memories or mutate a companion conversation. Decode greedily for initial controlled comparisons.

Ollama is an optional second provider for companion chat and prompt-only comparisons. Comparing an Ollama checkpoint against the pinned Transformers checkpoint is a separately labeled **model/provider comparison** with confounded checkpoint, quantization, and runtime differences. It cannot establish the isolated effect of personality methodology.

## 3. Target architecture

```text
React application: Companion | Studio | Memory | Setup
                          |
          One FastAPI application on loopback
                          |
     Context/personality composition + SQLite
                          |
      Shared bounded scheduler and job records
                          |
       One configured inference provider
             /                         \
 Existing Transformers runtime     Optional Ollama adapter
   scoped activation hooks          prompt capabilities only
```

Adopt FastAPI as the single HTTP layer because conversation, database, voice, and device routes already use it. Port the existing HTTP contracts and restrictions before switching the launcher. Retain the proven runtime/steering code and adapt the job manager instead of replacing its execution guarantees with direct async model calls.

This deliberately changes the earlier dependency-free HTTP-server decision. API/database dependencies become required for the unified backend; model and voice dependencies remain optional and lazy. The UI/setup must still run without model packages or a loaded model. Retain the self-contained file preview for interface-only use.

Use one process and one model worker; disable multi-worker serving and model-owning hot reload. The worker owns synchronous Transformers generation. Bridge events to FastAPI without blocking the event loop or using asyncio primitives unsafely from worker threads. An HTTP disconnect must not release model ownership before generation and hook cleanup finish. Multi-condition jobs hold exclusive access across all their legs.

Configure one provider per server launch initially. Switching providers requires a controlled restart, avoiding simultaneous model residency. Remove Figgy's hard-coded 24-hour Ollama residency policy from the shared design. No automatic fallback to another checkpoint, provider, or mock response. Test doubles remain in tests.

Proposed layout:

```text
apps/web/src/
  companion/ studio/ memory/ setup/ shared/
services/
  api/              # FastAPI app factory, lifespan, routes, HTTP policy
  inference/        # existing runtime, steering, generalized scheduler
  providers/        # common interface, Transformers and Ollama adapters
  personality/      # validated profiles, pure composition, fusion, mood
  conversations/    # orchestration, context budget, turn lifecycle
  memory/           # extraction, retrieval, episodic checkpoints
  storage/          # SQLite models and versioned migrations
  voice/ device/    # optional integrations, carried forward after text core
contracts/          # versioned API/export schemas and compatibility rules
tests/              # retained regressions plus integration coverage
scripts/            # one setup/launch path, migration and evaluation tools
docs/               # architecture, migration, source provenance, evaluation
```

Reuse `services` to minimize disruption to existing packaging. Move Figgy modules out of the generic `app` namespace; eliminate `sys.path` manipulation and import-time global provider/database creation.

## 4. Shared contracts and execution

- **Messages:** typed `system`, `user`, and `assistant` messages. Both providers receive structured history; do not concatenate `User:`/`Figgy:` transcripts into one user message.
- **Personality configuration:** immutable mode, persona IDs, normalized nonnegative finite fusion weights, intensity, mood setting, and profile version/hash. Require a positive fusion total and reject unknown IDs. Store defaults per conversation, snapshot per job, and avoid the current global mutable personality singleton.
- **Steering configuration:** recipe ID, strength, compatible model revision, and calibration profile. Advertise activation capability only for the supported local model. Reject unsupported requests explicitly; never ignore steering on Ollama.
- **Generation request:** frozen messages, decoding options, output budget, provider identity, steering, and cancellation handle. Provider events/results include text, usage when available, timing, and stop reason. Expose provider-specific context limits and capability flags.
- **Job:** single-turn or multi-condition type; bounded output/event retention; monotonic event IDs and full replay snapshots. Preserve idempotency, queue positions, stop acknowledgement, orphan timeout, and deadlines. A retry never creates another assistant turn or re-extracts memory.
- **Turn ordering:** allow one in-flight turn per conversation initially; return a clear conflict for overlapping submissions. Different conversations and studio runs share the scheduler. Reserve the turn and snapshot its context atomically before enqueueing; release reservations on failed admission.
- **Persistence:** persist turn/job association and statuses (`pending`, `complete`, `stopped`, `failed`, `interrupted`). Store partial output as partial, exclude it from normal history by default, and mark unfinished turns interrupted after restart. Never leave a database transaction open throughout slow generation or SSE delivery.
- **Completion:** a single finalization path records output and releases the conversation reservation on every outcome. Run tracked memory tasks only after the successful turn transaction commits, with fresh DB sessions; drain/cancel tasks on shutdown.
- **Readiness:** distinguish API liveness, provider availability, loading/calibration, and readiness. A model error cannot appear as healthy inference.

Context budgeting is an early integration gate. Start with the existing 768-token Qwen input cap; account for system instructions, memories, history, current user text, and template overhead using the actual tokenizer. Keep the current user message and required instructions, then fit bounded memories and the newest complete history turns. If mandatory content alone does not fit, return an actionable error. Use compact, versioned persona rendering where necessary. Increase the runtime limit only after an explicit memory/latency pilot, never by copying Figgy's 4,096 setting.

Proposed API boundaries:

| Routes | Purpose / compatibility |
| --- | --- |
| Existing `/api/runtime`, `/api/runtime/load`, `/api/recipe`, `/api/examples` | Preserve setup and existing studio behavior |
| Existing `/api/comparisons` and job GET/events/DELETE | Keep version-1 two-leg compatibility |
| `/api/v2/experiments` and job GET/events/DELETE | Named conditions and expanded provenance |
| `/api/v2/conversations` and conversation GET | Create/list/load conversations |
| `/api/v2/conversations/{id}/settings` | Conversation-specific persona/memory defaults |
| `/api/v2/conversations/{id}/turns` and shared job routes | Submit, stream/reconnect, stop chat turns |
| `/api/v2/personas`, `/api/v2/memories` and memory DELETE | Catalog and scoped memory management |

Update the Figgy CLI to the shared client contract. Do not silently keep the global semantics of `/v1/persona`; document migration of the old Figgy endpoints. Preserve existing Neuron DJ API behavior while introducing v2 independently.

## 5. Memory, security, and compatibility work

Figgy currently retrieves recent semantic/episodic entries globally; `user_message` does not affect ranking. Fact extraction is regex-based, and episodic “summaries” concatenate old message snippets without removing/checkpointing old history. Preserve this as a modest initial memory mechanism, improve its boundaries, and describe it accurately.

Scope semantic facts to the local owner profile and episodes to a conversation. Add unique scoped keys and source-message references. Retrieve a bounded set using simple relevance plus recency; do not add embeddings for the initial merge. Checkpoint compaction so old segments are not repeatedly processed. Enforce scope on reads/deletes. Delete source-linked derived memory when deleting its source under the documented deletion policy, so deleted facts are not automatically recreated from retained history.

Retain Neuron DJ's loopback binding, host/origin validation, request bounds, no-store headers, and privacy-conscious logging in FastAPI. Replace Figgy's wildcard CORS defaults; render stored content as React text, not interpolated `innerHTML`. Remote/device exposure is a separate configured mode with authentication, not the default launcher behavior.

Preserve the current cache and calibration paths. Keep port 8791 and the current browser storage keys so saved recipes/comparisons remain discoverable. Read v1 recipes/replays and retain their historical meaning; write richer v2 records without adding persona instructions to old records. Settings-only exports must still exclude messages, memories, and responses. Recorded replay exports remain explicit.

Introduce a root-relative database path under ignored application state. If an existing Figgy database is found, back it up and migrate a copy with versioned, repeatable migration steps. Assign legacy unscoped memories to the local default profile. No database was found in the reviewed tracked/source file inventory. Do not auto-delete the cloned repository or its nested Git history.

Record Figgy's source revision `376ccad` and preserve attribution/notices. The outer workspace currently has no Git repository; the clone has its own clean history. Treat consolidation of source code and consolidation of history as distinct tasks. Preserve `.artifacts/history.fi`; do not run the old history importer or overwrite nested metadata as part of the merge. No top-level license file was found in the clone during review; resolve redistribution metadata before any later publication.

## 6. Implementation sequence and acceptance gates

| Milestone | Implementation | Depends on | Acceptance gate |
| --- | --- | --- | --- |
| 1. Foundation and contracts | Consolidate package/extras/config; record provenance; introduce app factory and provider/message/config schemas; install and establish Figgy test baseline | This plan | Existing 33 Python and 15 JS tests plus typecheck remain green; Figgy tests run with isolated DB/provider state; API starts without ML/voice packages |
| 2. Unified execution | Port current HTTP routes to FastAPI; adapt provider and scheduler for structured messages and single-turn jobs; retain v1 comparisons | 1 | Existing HTTP behavior survives migration; one worker; queue/cancellation/reconnect tests; unchanged baseline and zero-strength/recovery checks; cleanup failure retires runtime |
| 3. Companion vertical slice | Port pure persona composition, SQL storage/migrations, bounded context, turn state and memory; add React chat/persona/memory views | 2 | Two isolated conversations; five personas and valid fusion; persona changes preserve history; chat survives restart; no duplicate turns on retry; stopped output visibly partial; memory inspection/deletion works |
| 4. Studio methods | Add v2 condition snapshots, two/four-condition jobs, method controls, metrics, recipe/export compatibility | 3 | Four conditions use the same checkpoint/settings; runs do not mutate chat/memory; cancellation works between and within legs; v1 imports still work; all provenance is frozen |
| 5. Optional Ollama and client consolidation | Adapt Ollama to structured messages/settings/capabilities; migrate CLI; use one setup/start flow and retire duplicate dashboard from active use | 3, 4 | Missing Ollama gives actionable setup status; activation requests rejected; actual model identity recorded; no fallback or second in-process model owner; clone kept as reference until parity is checked |
| 6. Real-model integration pilot | Exercise companion and studio on cached Qwen; verify MPS in a normal terminal if available; measure context, cancellation, latency, and memory | 4, 5 | Real streamed chat and comparison; fresh-state baseline recovery; no cross-job hooks; measured peak memory/time-to-first-token/tokens-per-second; limits reported honestly |
| 7. Optional voice/device carry-forward | Move existing voice/device APIs behind feature extras and shared conversation path; remove global persona coupling; bound uploads and offload synchronous STT | Text acceptance | Text app works without voice packages; voice/device tests use same context/provider rules; unsupported hardware is explicitly identified |

Milestones 1–6 define the unified text-project release. Milestone 7 preserves the clone's additional capabilities as a follow-up rather than making hardware a prerequisite. Firmware, wake-word/offline device behavior, remote tunnels, adapter training, and additional neuron discovery remain separate work.

The existing voice code awaits the complete LLM reply, buffers TTS audio, and returns base64 JSON from voice chat. It does not implement end-to-end streaming audio or interruption. Its `edge_tts` integration must have network behavior documented before enabling it; do not describe the whole application as offline when a configured voice provider uses an external service. Voice latency claims in the clone README are not measurements of this merged project.

## 7. Verification and risks

Baseline checks performed during this planning pass:

- `.venv/bin/python -m unittest discover -s tests -v`: **33 passed**, including tensor steering and tiny real-Qwen architecture tests.
- `npm test`: **15 passed**, exercising the current production UI bundle.
- `npm run typecheck`: **passed**.
- Figgy tests not run: this `.venv` lacks pytest, FastAPI, SQLAlchemy, aiosqlite, HTTPX, voice libraries, and related dependencies. No packages installed during planning.
- No full-model load or live browser/API check performed in this pass. Earlier recorded CPU runs took about 299 seconds for 16 tokens per leg; GPU behavior is still an explicit verification gate, not a promised performance improvement from the merge.

Regression tests should focus on real boundaries: async/thread handoff, cancellation while generating, cleanup failure, full queue/replay gap, idempotent DB writes, same-conversation concurrency, cross-conversation isolation, malformed fusion weights, token budgeting, interrupted turns, data migration, provider capability rejection, origin/host restrictions, and v1 export compatibility. Keep provider mocks confined to tests and distinguish them from live-model evidence.

Run a small matched pilot before a large behavior sweep: baseline/prompt/activation/combined on a few ordinary prompts, then persona switching and multi-turn memory. Record coherence, persona adherence, factual quality, timing, and recovery separately. A 16 GB machine may not support the desired context and latency with the current unquantized runtime. Ollama may offer a different deployment profile, but activation recipes cannot be transferred to it merely by matching a model name.

## 8. Decisions and remaining assumptions

Confirmed: companion plus studio in one application; plan before implementation.

Recommended defaults: Mac first; current pinned Qwen as primary; FastAPI single backend; existing React frontend; prompt-only companion by default; explicit experimental activation control; Ollama optional; text integration before voice/hardware. No final project rename is needed for the technical merge.

Windows/RTX 3050 support, exact Ollama checkpoint/quantization, final voice provider, and physical hardware remain open follow-up decisions. The initial implementation can proceed on the stated defaults without claiming support for those untested targets.
