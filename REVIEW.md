# Neuron DJ review — 2026-10-31

Follow-up on November 7: the model packages and checkpoint are now installed. Real CPU loading, calibration, recovery checks, and short paired generation completed. Loading progress, CPU selection, startup, and several UI defects were fixed. See [the loading investigation](docs/LOAD_CHECK.md) for current measurements and remaining limits. The notes below describe the earlier review.

Reviewed the interface, local runtime, calibration cache, queue lifecycle, cancellation, retained results, and reconnect behavior. Changes are implemented in source and the production preview bundle.

## Findings resolved

| Finding | Change |
| --- | --- |
| Expired or restarted jobs could leave the browser stuck in an active run after SSE failure. | Check the job endpoint after stream failure; a 404 releases the controls and preserves already received text with an explanation. A terminal response closes the stream and enters session history. |
| Structurally invalid calibration JSON could prevent model startup. | Validate the document and units before reuse; recompute malformed or incompatible caches. Boolean units are rejected. |
| Runtime status exposed mutable profile/calibration objects to callers. | Return independent copies. |
| Expired terminal jobs were pruned only by another submission. | The watchdog now removes expired jobs and associated idempotency keys. |
| Rejected submissions could evict retained results prematurely. | Reserve retention capacity only after admission checks pass. |
| Waiting clients did not receive updated queue positions. | Emit queue snapshots when an earlier queued job is cancelled or dequeued. |
| A request already cancelled before generation could still reach model setup. | Return a stopped result before importing generation dependencies or touching the model. |
| Opening a replay could retain a previous recipe's calibration constraint. | Restore the recorded runtime profile, or clear the constraint if absent. |
| Invalid recipe names could throw during direct file export. | Report the validation error within the interface. |

## Interface changes

- Larger body text, response text, controls, and touch targets; clearer graphite, lime, cyan, and amber hierarchy.
- Task order: mix, prompt, comparison. DOM and keyboard order match the visual order.
- Side-by-side or single-response views, with both outputs preserved.
- Copy actions on each deck and automatic scrolling that yields when the reader scrolls up.
- Frozen run prompts and a restore-settings action distinguish displayed results from the next run.
- Five recent comparisons in tab memory, with explicit guidance to save persistent copies.
- Offline primary action opens setup instead of leaving the user with a disabled run button.
- Skip-to-prompt link, labelled response regions, pressed-state controls, responsive layouts, and reduced-motion support.

## Verification

- Production UI bundle: **11 JavaScript tests passed**. Includes copying, view switching, prompt ordering, snapshot restoration, session replay, expired-stream recovery, storage failures, and recipe/replay validation.
- Python: **25 tests passed**, including the real PyTorch activation test using an existing local Python environment. No model weights are needed by these tests.
- TypeScript check and production build passed.
- Test response fixtures remain confined to tests; the product has no simulated model outputs.

## Remaining verification limits

The pinned Qwen checkpoint is not cached, and the project environment has not completed its model dependency install. Full-model generation, MPS compatibility and memory fit, local calibration, steering behavior, and latency still require the live pilot described in README.md. Passing tensor and queue tests does not establish those results.

The execution environment cannot bind a localhost service, and browser access is unavailable. TCP integration, rendered visual inspection, responsive overflow, and real-browser keyboard/scroll behavior remain unverified. DOM tests exercise interaction state, not browser geometry.

Git metadata is read-only in this workspace. Conventional milestone snapshots are prepared in `.artifacts/history.fi` using the configured Git identity, without AI attribution trailers; they are not yet actual commits. The documented importer can create the history when Git writes are available.
