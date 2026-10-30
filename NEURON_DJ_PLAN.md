**Neuron DJ — product and delivery plan**

Prepared 30 October 2026. Status: planning only. This document is separate from the existing `EXPERIMENT_PLAN.md`, which remains unchanged. Three research agents reviewed steering feasibility, product experience, and architecture/delivery. No application code, package installation, model download, inference run, Git initialization, or deployment is part of this planning phase.

**1. Product promise**

Neuron DJ is an instrument for exploring how a reversible activation intervention changes a model's responses. The user writes one prompt, chooses a validated recipe and strength, and compares the original and modified outputs under matched generation settings.

The core loop is: choose a prompt → set a mix → run both → compare → adjust → save or share settings.

The first release should feel like polished, slightly ominous studio equipment: graphite surfaces, restrained colored accents, readable response decks, and one useful fader. The interaction itself provides the spectacle. Quantitative personality scores, decorative brain scans, and unsupported labels would weaken the experience.

Activation steering describes the mechanism. A hostile persona does not, by itself, demonstrate a successful safety jailbreak or a change in capability. We will describe observed behavior without presenting a tone change as a broader research result.

**2. Decisions and assumptions**

| Area | Proposed decision | Reason or gate |
| --- | --- | --- |
| First delivery | Local UI, local inference, and local recipe storage on the user's Mac | User-confirmed target; Mac fit and responsiveness must be measured |
| Model | One pinned Qwen3.5-4B checkpoint | Direct relationship to the published steering work |
| Runtime | Python, PyTorch, and Transformers candidate; device/dtype selected by pilot | Internal activation access and implementation transparency |
| Comparison | Single-turn, original versus steered, deterministic decoding by default | Shared input and settings make differences easier to interpret |
| Controls | One published two-neuron recipe and one strength fader | Independent personality axes have not been established |
| Concurrency | One loaded model, one active paired job, sequential response generation | Low-memory starting point with controlled intervention isolation |
| Persistence | Browser-local recipe storage; explicit saving of comparison records | No accounts or database needed for a useful first version |
| Web UI | React, TypeScript, static build; Vite is the candidate development tool | Interactive client state without requiring an application server for the UI |
| Public hosting | Later: Sites for the UI/gateway and a separate inference service | Web hosting and model execution have different resource requirements |

The existing research plan identifies a 16 GB M2 Pro. This session has not re-benchmarked that hardware. Official model files total approximately 9.34 GB, which does not establish that inference will fit in available unified memory. Loading buffers, activations, caches, and other applications add overhead. [Official checkpoint files](https://huggingface.co/Qwen/Qwen3.5-4B/tree/main).

The product does not depend on finishing the existing four-condition research study. Keep product calibration prompts, demo prompts, and engineering smoke checks separate from that study's locked test set.

**3. MVP scope**

The local MVP includes:

- A responsive two-deck workspace labeled Original and Remix.
- One validated persona recipe, reset, and a strength fader limited to the tested range.
- Strength presets clearly presented as variations of that same recipe.
- A shared prompt composer and a small set of ordinary starter prompts.
- Live streamed output, explicit queue/execution state, and a Stop action.
- Immutable settings attached to every comparison.
- Genuine recorded examples, labeled persistently as recorded playback.
- Recipe saving, validated import/export, and provenance details.
- Explicit comparison export with prompt and outputs included only when chosen.
- Keyboard operation, responsive mobile layout, and reduced-motion support.

Do not include multi-turn branching, neuron-discovery sweeps, refusal-ablation controls, fine-tuning, model tools, voice, multiple simultaneous models, account systems, billing, or a public marketplace in this milestone. Additional independent personality controls require separate evidence and validation of combinations.

**4. The first minute**

Open directly into the instrument. A real saved comparison is visible with a persistent Recorded example label, the prompt, both outputs, and the recipe strength that produced them. These examples will be generated only after a runtime and recipe have passed validation; placeholder content must not masquerade as model output.

The main instruction is: “Adjust the strength, then compare both responses.” Starter chips might offer planning a Monday, explaining an ordinary concept, or a short self-description. They should be varied enough to show that the effect can depend on the prompt.

The user can inspect an example, understand the fader, edit the prompt, and submit a live comparison within a minute when the runtime is ready. This is an onboarding goal, not a promise of live generation completion within a minute on unbenchmarked hardware.

When the model is loading, preserve the example and show the actual loading state. Do not display an invented progress percentage. A disconnected runtime leaves the instrument and saved examples usable, with live generation clearly unavailable.

**5. Screen and interaction design**

Desktop has a compact header with runtime status, a narrow recipe rail, two equally prominent response decks, a shared prompt composer, and a mixer strip. The strip holds the strength fader, its numeric multiplier, reset, and the primary Run comparison button. A details drawer holds the technical information.

Use graphite backgrounds, a cool cyan accent for Original, and a warm amber accent for Remix. Body text uses a readable sans-serif; monospace is reserved for technical values. Status always has a text label in addition to color. Motion acknowledges actions without competing with reading.

A linear fader is the first control. It is discoverable, works on touch screens, and maps cleanly to keyboard input. Show a dose multiplier such as 0.5× relative to the recipe, not a supposed percentage of evil. The initial range is bounded by product validation; 0 to 1× is a candidate, not an entitlement to expose the full published dose if it degenerates.

The recipe rail initially contains the published recipe and tested strength variants. Do not imply that several strengths are several independently discovered personalities. The advanced drawer exposes neuron coordinates, recipe source/version, calibration profile, model revision, precision, and generation details. Independent component editing is deferred until supported combinations have been tested.

When a comparison starts, snapshot all settings. Controls may remain editable, but edits show Applies to next run. Displayed responses keep their original snapshot visible. Editing a fader must not change the interpretation of tokens already generated.

The first backend generates sequentially. Show Generating original while Remix says Waiting for original, then show Generating remix. Both decks remain visible. Side-by-side display must not imply simultaneous model execution.

On mobile, collapse recipes into a sheet, stack the response decks, and keep the composer and mixer reachable. An optional A/B reading switch may come later. Avoid shrinking two desktop columns until neither response is readable. Ensure visible focus, standard keyboard fader behavior, large touch targets, zoom/reflow, and restrained screen-reader announcements. Do not announce every streamed token.

**6. Waiting, cancellation, and recovery**

Use explicit runtime states: disconnected, loading, ready, and unavailable. A comparison has queued, running-original, running-remix, stopping, complete, stopped, and failed states. Each deck has its own completion/partial status.

Queue position is shown only when the backend knows it. Do not invent countdowns. Stop changes the UI to Stopping until the model worker acknowledges that generation has actually ended. Partial responses remain visible and exportable with partial status.

A failure in Remix preserves a completed Original. Preserve the prompt, settings, and any received output after network failure. Reconnection attaches to the existing job; it must not silently start a second generation. Retrying a comparison creates an explicit new paired run.

Never substitute a prompt-based persona or mock response when activation steering is unavailable. Recorded playback, live inference, and future prompt-based experiments are distinct modes and must be labeled accordingly.

**7. Runtime feasibility gate**

Before promising a polished live experience, perform a small engineering pilot. Use a pinned checkpoint and compatible dependency versions, verify the text-only non-thinking template, start with batch size one and short bounded input/output, and record the actual environment. The official model card documents thinking-mode configuration. [Qwen model card](https://huggingface.co/Qwen/Qwen3.5-4B).

The original explorer is a useful implementation reference for local inference and activation access. The separate reproduction documents the published paired intervention. Reuse only the small relevant primitives if appropriate, with upstream license notices preserved; do not import the entire explorer into the product. [Original runtime](https://github.com/lyramakesmusic/neuron-explorer/blob/main/explorer/runtime.py), [published reproduction](https://github.com/shmuelamar/evil-qwen).

Proposed pilot acceptance checks:

1. Load the baseline and produce coherent output with correct stopping behavior.
2. Verify the intervention's insertion location and coverage of prompt processing and token decoding.
3. Check zero strength against the unmodified baseline within a documented dtype-appropriate numerical tolerance.
4. Run baseline → modified → baseline and verify recovery.
5. Repeat the recovery check after cancellation and injected generation exceptions.
6. Verify that each leg starts with fresh attention/recurrent state and no intervention or RNG leakage.
7. Complete repeated paired jobs without accumulating memory or stranded generation workers.
8. Test a small development panel across candidate strengths; record tone changes and degeneration separately.

Use an initial panel of about 20 benign prompts across zero and several dose levels, followed by about 20 held-out benign prompts to check the selected labels and range. If runtime is costly, stage the panel after the first load/recovery checks. This is product validation, not the formal safety experiment.

Measure cold load time, warm time to first token for each deck, total pair completion time, tokens per second, peak memory, stop latency, failure rate, and memory behavior across runs. Establish supported input/output budgets from those measurements. Do not claim exact cross-device output reproducibility.

The gate passes only with a useful, coherent, repeatable contrast and clean model recovery. A visible difference alone does not validate a specific personality label. If the full model is too constrained, investigate a lower-memory local runtime. A quantized or MLX implementation is a separate runtime profile requiring renewed hook/calibration checks. If no useful local configuration is feasible, report the measured limit and propose alternatives before changing the user-confirmed local target. Preserve an inference API that could later support a remote GPU; remote execution is not part of the initial delivery. Kaggle can support validation but is not the assumed persistent product API.

**8. Application architecture**

Keep four clear areas in the eventual repository:

| Area | Responsibility |
| --- | --- |
| apps/web | React/TypeScript instrument, run state, streaming client, local recipes, exports |
| services/inference | Model loading, validated intervention profiles, generation worker, bounded queue, cancellation |
| contracts | Versioned recipe, comparison request, stream event, and saved comparison schemas |
| docs | Runtime measurements, design decisions, setup, compatibility notes, deployment requirements |

During development, use a same-origin frontend proxy to the loopback inference service. For normal local use, the Python service can serve the compiled static UI and inference endpoints together, avoiding a separate Node server. This also avoids making a public website depend on browsers reaching a user's localhost. Do not add SSR, a central database, or a distributed queue to the local MVP.

The local startup experience should have one documented launch command after installation. First use checks available storage and runtime support, explains the model download and cache location, and keeps recorded examples available during loading. Subsequent launches reuse the cached model. Prompt generation and saved recipes stay on the Mac; no cloud key or external prompt service is required. Run one model-owning process, including during development: frontend hot reload must not create duplicate model copies. Native app packaging is a later convenience, not a prerequisite for the browser-based local product.

The backend exposes runtime health/capabilities, comparison submission, event subscription, and cancellation. Capabilities include the actual model profile, ready state, validated recipes, supported strengths, and input/output limits. The frontend obtains these values instead of inventing a universally available control range.

A comparison is one atomic job with an immutable request. Both legs use the same prompt, system/template configuration, model revision, context budget, and decoding parameters. Default to deterministic decoding. Optional sampling can be added later with recorded settings and fresh per-leg RNG initialization.

One dedicated worker owns model execution. Hold exclusive model access across both legs. Install steering only within the active scope and restore the model on completion, failure, or stop. For Qwen's hybrid architecture, fresh state includes any recurrent state as well as attention caches. Releasing an HTTP request is not sufficient to release a model lock: the generation thread must have stopped and cleanup must be complete before the next job starts.

Stream events carry job identity, immutable configuration identity, response side, event sequence, and event type. Use a fetch-consumed server-event stream with bounded event retention and a deliberate reconnect policy. The backend supports idempotent submission, bounded queue length, job expiry, and cancellation checks during generation. Late events from an old job cannot overwrite a newer comparison. [Server-sent events reference](https://developer.mozilla.org/en-US/docs/Web/API/Server-sent_events/Using_server-sent_events).

Do not cache baselines in the first implementation. If caching becomes necessary, key on the full model/runtime/template/input/decoding fingerprint, distinguish cached output in provenance, and validate that it preserves the intended comparison semantics.

**9. Recipe and comparison records**

A recipe is versioned data: display name, evidence status, source, model/checkpoint compatibility, intervention implementation/version, component identifiers, coefficients, calibrated strength limits, calibration identifier/hash, runtime/precision profile, and a canonical configuration hash.

Import accepts only supported schemas and validated values, with bounded size. Do not accept executable content, arbitrary module paths, or unbounded intervention coordinates from a shared file. Incompatible model/runtime/calibration profiles produce a clear explanation and cannot silently run as if equivalent.

A saved comparison adds the exact prompt/input, template identity, decoding configuration, outputs, partial/completion status, stop reason, timings, and environment signature. Saving settings and saving text are separate actions. The default recipe save does not include prompts or responses; comparison saving is explicit.

Start with browser-local storage: small recipes/settings can use local storage and comparison records can use IndexedDB if their size warrants it. No server-side prompt retention is needed for the local MVP.

Settings-only links or files are the first sharing mechanism. Prompt and output replay exports require a preview of exactly what is included. Stored-output playback and fresh inference are separate actions. Opening an imported recipe never automatically starts inference.

Public hosted replay pages, deletion controls, and durable shared storage follow later if needed. Avoid building accounts solely to support the initial local workflow.

**10. Verification and definition of done**

Backend checks focus on intervention location, zero-strength behavior, cleanup, request isolation, stopping, bounded admission, and fresh per-leg state. Tests should assert meaningful properties, not require a particular hostile sentence or brittle exact prose across devices.

Contract checks cover invalid/incompatible recipes, schema versions, job identity, stale stream events, reconnection, duplicate submission, and stopped/failed output semantics. UI journey checks cover first use, submission, editing settings during a run, cancellation, network failure, importing a recipe, saving/exporting, and desktop/mobile keyboard use.

The local release is done when a new user can understand the two conditions, run a real comparison, identify the strength used for each pair, change settings without misreading old output, stop generation, recover from failure, and save/reopen a compatible recipe. The startup instructions must work from a clean environment with model downloads and resource needs documented.

For the public beta, add measured load/cost checks, supported concurrency, bounded queue behavior, token/request limits, server-held inference credentials, origin restrictions, and an operator stop control. Log operational timing/status without storing prompt text by default. These are features of the hosted path, not reasons to build an account platform for local use.

**11. Structured commit sequence**

Initialize Git only when implementation starts. Use the user's configured Git identity. Commit subjects follow conventional commits; each commit has one reviewable purpose and includes checks relevant to its changes. Do not add Codex attribution, AI coauthor trailers, or generated-by footers.

| Order | Commit subject | Reviewable result / exit criterion |
| --- | --- | --- |
| 1 | docs: define Neuron DJ scope and delivery gates | This product plan and architecture decisions recorded; existing research plan preserved |
| 2 | chore: scaffold web and inference workspaces | Minimal development structure and contracts location; ignored caches/model files; environment examples |
| 3 | feat(runtime): add pinned baseline inference pilot | Coherent baseline; environment, memory and latency measurements; documented Mac runtime decision |
| 4 | feat(steering): add scoped reversible persona intervention | Verified prompt/decode coverage, zero-strength recovery, cleanup after failure/stop, validated initial range |
| 5 | feat(api): add queued cancellable comparison jobs | Immutable paired jobs, one worker, bounded admission, streamed events, idempotency and real cancellation |
| 6 | feat(ui): build accessible mixer and comparison workspace | Responsive instrument, readable decks, fader, prompt composer, state presentation; any fixtures clearly marked |
| 7 | feat(compare): connect live paired response streaming | Real end-to-end Original/Remix generation, pending settings, stale-event protection and recoverable failures |
| 8 | feat(recipes): add validated presets and local persistence | Tested strength variants, compatibility enforcement, saving/import/export, genuine recorded examples |
| 9 | feat(sharing): add recipe links and explicit replay exports | Settings-only sharing, export preview, provenance, recorded/live distinction |
| 10 | test: verify comparison isolation and critical user journeys | Cross-stack cancellation/reconnect/isolation and mobile/accessibility coverage; gaps closed without deferring earlier checks |
| 11 | docs: document operation and deployment requirements | Clean setup, measured supported limits, troubleshooting, and a concrete hosted deployment specification |

The baseline and steering commits are sequential technical gates. UI work can proceed after the contract and validated behavior are understood. Do not race a polished interface ahead of an unverified steering backend. A dedicated integration-test commit does not postpone correctness tests needed by earlier commits.

Public deployment is a later scoped increment once the destination, GPU budget, and measured workload are known. It should receive separate infrastructure/deployment commits, not be hidden inside documentation or a generic cleanup commit.

**12. Delivery sequence and estimates**

| Stage | Work | Gate |
| --- | --- | --- |
| Runtime pilot | Baseline load, intervention, recovery, measurement, small dose panel | A viable runtime and coherent effect; schedule depends on compatibility |
| Vertical slice | One prompt from browser to real paired streamed responses | Real comparison, stop, and immutable settings work end to end |
| Product pass | Instrument styling, first use, responsive layout, recipes/examples, recovery | A first-time user can use the instrument without neuron knowledge |
| Local release | Persistence/export, integration checks, clean setup and measured limits | Local definition of done passes |
| Hosted beta | Sites frontend/gateway plus suitable persistent inference service | Hosting target/budget chosen; load and operational controls verified |

Allow approximately 6–10 focused working days for the local product after runtime viability is established. This is a planning allowance, not a promised calendar date. Mac-specific runtime work and quantization ports are separate uncertainties. Timebox the first full-model pilot to roughly one or two focused days, then decide whether a lower-memory local profile needs a separate validation phase. Do not silently switch to remote inference.

Sites/Cloudflare Workers can serve the web experience and forward requests, but the standard Worker isolate has a documented 128 MB memory limit. Model weights and execution belong in the separate inference service; stream its output through the gateway without buffering entire generations. Do not put GPU credentials in the browser. [Cloudflare Worker limits](https://developers.cloudflare.com/workers/platform/limits/).

**13. Next enhancements after the core loop works**

Blind A/B voting can conceal condition labels until the user chooses a response, then reveal the settings. A small setlist can compare the same recipe across three ordinary prompts with compute use explicit. Text-difference highlighting can assist reading, while making clear that lexical change is not an evaluation of personality or safety.

Add further personality recipes only after verifying their behavior, coherence, compatibility, and combined effects. A later multi-turn mode needs a clearly defined shared-history or branch-history model and renewed state/isolation checks. These features should build on the validated instrument rather than delay its first usable release.

**14. Remaining decisions**

The first deployment target is confirmed: fully local on the user's Mac, with local inference and storage. Visual tone defaults to polished dark studio equipment. Exact runtime versions, precision/quantization profile, strength limits, supported prompt/output lengths, and latency targets will be set from the pilot. Public hosting and GPU spend are outside the initial release and would be separate later decisions.

Implementation begins with the baseline and steering feasibility gates after this planning phase. No code or commits have been created as part of preparing this document.
