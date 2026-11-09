Version 1 contracts are defined by `services/inference/contracts.py` and mirrored in `apps/web/src/types.ts`. A comparison freezes prompt, strength, token budget, recipe identity, and runtime provenance. Events carry monotonically increasing IDs and full bounded job snapshots so reconnects cannot lose already generated text. Recipe exports contain settings only; replay exports separately contain the prompt and outputs. Neither imported file type can select a model path or execute code.

Version 2 contracts live in `services/inference/work.py`. A job contains immutable named legs, each with typed system/user/assistant messages and a steering strength. Common output limits and persona provenance are frozen at admission. All jobs share the existing scheduler and runtime profile snapshot.

Unified API (JSON request bodies, same local origin, 32 KiB maximum):

| Method/path | Request | Response |
| --- | --- | --- |
| GET `/health` | — | API liveness and inference state separately |
| GET `/api/v2/personas` | — | `{personas: [{id,name,description}]}` |
| POST `/api/v2/conversations` | `{title?: string}` | 201, conversation with `id`, `settings`, `turns` |
| GET `/api/v2/conversations` | — | `{conversations: [...]}` |
| GET `/api/v2/conversations/{id}` | — | Persisted conversation plus live turn snapshots |
| PUT `/api/v2/conversations/{id}/settings` | Complete settings object | Validated normalized settings for subsequent turns |
| POST `/api/v2/conversations/{id}/turns` | `{message: string}` plus `Idempotency-Key` header | 202, queued chat job; 409 for overlapping or conflicting retry |
| POST `/api/v2/experiments` | `{prompt, settings?, conditions?}` plus `Idempotency-Key` | 202, sequential experiment job |
| GET `/api/v2/jobs/{id}` | — | Job snapshot; 404 after retention or restart |
| GET `/api/v2/jobs/{id}/events` | Optional `after` query or `Last-Event-ID` | SSE `snapshot` events with full job and monotonic event IDs |
| DELETE `/api/v2/jobs/{id}` | — | Stop acknowledgement; ownership retained through cleanup |
| GET `/api/v2/memories` | — | `{memories: [...]}` for local profile |
| DELETE `/api/v2/memories/{id}` | — | `{deleted: true}` |

Settings fields: `persona` (one catalog ID), `fusion` (map of persona IDs to finite nonnegative weights with positive total, or empty), `intensity` (0–1), `mood` (boolean), `memory` (boolean), `strength` (0–1), and `max_tokens` (16–256). Defaults come from `Personality`. Fusion values are returned normalized.

Experiment conditions are two to four distinct names from `baseline`, `prompt`, `activation`, and `combined`; default is all four. Memory and history are always excluded from studio jobs in this release. Activation strength zero remains allowed as a recovery/control condition. Nonzero activation requests require an activation-capable provider. The existing v1 comparison route requires the original Transformers recipe/provider.

Chat job outputs use `reply`; experiments use their condition names. Status transitions are `queued` → `running-{leg}` → `complete`, with `stopping` → `stopped` or `failed` as applicable. Persisted unfinished chat turns become `interrupted` on restart and retain their last checkpoint. Terminal chat retries with the same key return the saved result, including after job expiry/restart, without re-generating or re-learning facts. Experiment idempotency is bounded by in-memory job retention, as with v1 comparisons.

Errors use `{error: string}`: 400 invalid data/capabilities, 403 origin/host mismatch, 404 missing record, 409 turn/key conflict, 413 body limit, 415 content type, 429 queue/stream capacity, and 503 model unavailable. Setup/runtime and v1 comparison routes retain their original paths. The standalone Figgy `/v1/*` routes are not aliases; use the unified CLI or these explicit conversation-scoped routes.
