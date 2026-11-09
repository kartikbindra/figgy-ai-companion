# Loading investigation — 2026-11-07

## Follow-up: GPU calibration failure fixed — 2026-11-10

The running service reported `Model load failed (ValueError): Calibration produced an invalid residual or column norm.` after 130.246 seconds, with `loading_device=mps`. The HTTP server remained alive. This current failure occurred during FP16 calibration; it is distinct from the earlier native MPS weight-conversion crash below.

Changed the default MPS dtype to BF16, matching the checkpoint's stored precision and CPU profile. Kept sequential MPS loading enabled. Reject explicit FP16 overrides before allocating weights. Calibration now reports the layer and runtime profile immediately upon detecting nonfinite activation norms, and reports the actual median/column norm for other invalid coefficients. Failure cleanup drops model/submodule references and collects cached MPS allocations after exception traceback cleanup.

Real checkpoint verification on this Mac, using Torch 2.14.1 and Transformers 5.20.0:

- MPS/BF16 loading, six calibration prompts, finite logits, zero-strength equivalence, and baseline recovery all passed in **38.572 seconds**.
- A real HTTP comparison completed with 16 tokens on each leg: Original **13.597 seconds**, 0.25× Remix **1.773 seconds**. The first leg includes cold execution overhead; this is not evidence that steering improves speed. Outputs intentionally stopped at the short token limit.
- The recorded comparison is retained locally in `.neuron-dj/mps-bf16-verification.json`; logs are in `.neuron-dj/load-check.log`. These local artifacts are ignored by Git.

Regression coverage checks BF16 selection, preservation of sequential MPS loading, rejection of FP16 before model allocation, and calibration hook cleanup on nonfinite activations. No model download or dependency upgrade was required.

The reported issue was that the model would not load. The local URL returned `ERR_CONNECTION_REFUSED` in native Chrome during inspection. The pinned checkpoint files and all model packages are present in the project's Python 3.12 environment. A direct model test succeeded; GPU execution is unavailable to the command environment used for this investigation.

## Observations

- Full Qwen3.5-4B loaded on CPU/BF16, calibrated six prompts, and passed finite-logit, zero-strength, and baseline-recovery checks in **217.124 seconds**.
- Prompt: “Describe a quiet morning in one sentence.” Original generated 16 tokens in **298.976 seconds**; the 0.25× Remix generated 16 tokens in **297.146 seconds**. Both stopped at the token limit. This establishes that the cached model and generation path work; it is not a useful interactive CPU speed or a persona quality evaluation.
- The older November 1 crash report shows `SIGSEGV` in PyTorch's MPS shader cache while converting/copying weights. The existing `HF_DEACTIVATE_ASYNC_LOAD=1` guard is preserved and covered by tests. A current GPU run is needed to establish whether that failure remains.
- Native Chrome rendered the preview and setup panel. The live local service was not running at the default URL. This execution shell cannot bind a server port, and the computer-use tool denies Terminal access.

## Changes

- Calibration calls the base model, avoiding vocabulary scores it does not use. Recovery checks calculate only last-token logits. Tests with a tiny real Qwen architecture verify identical calibration coefficients and last-token logits.
- Loading reports its device, elapsed time, calibration prompt number, recovery-check number, and original exception instead of a static loading message or misleading cache error.
- Model setup places the load action first and offers explicit CPU recovery. Validation rejects unsupported devices before starting a loader.
- The launcher rebuilds changed UI sources, opens the browser with `--open`, supports `--cpu`, and explains port-permission/conflict failures. `Neuron DJ.command` offers a double-click entry point on macOS.
- The file preview clearly identifies its offline state and links to the local app.
- Fixed accidental dialog closure when clicking padding, notifications hidden behind modal dialogs, invalid recorded examples crashing the library, unsupported imported response lengths displaying incorrectly, and overlapping sidebar content.

## Checks and next launch

**33 Python tests and 15 JavaScript tests passed**, including real tensor checks, tiny-Qwen calibration equivalence, CPU load requests, progress display, malformed examples, and modal behavior. TypeScript and production build passed.

From the project directory in a regular terminal:

```sh
python3 scripts/start.py --open --load-model
```

If GPU loading fails or terminates the service, restart with:

```sh
python3 scripts/start.py --cpu --open --load-model
```

Use the HTTP app, keep that terminal running, and allow loading/calibration to finish. CPU is a diagnostic/recovery option and was very slow in this session. GPU loading and live browser/API streaming remain to be verified.

A follow-up load with the updated recovery-check code reused the CPU calibration and reached `ready` in **80.702 seconds**, with all smoke checks passing. This timing includes a cache reuse and is not a controlled speed comparison with first-time calibration.
