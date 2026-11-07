**Runtime profile**

The model and tokenizer are pinned to `Qwen/Qwen3.5-4B` revision `851bf6e806efd8d0a36b00ddf55e13ccb7b8cd0a`. Loading uses `Qwen3_5ForConditionalGeneration`; the layer path is `model.model.language_model.layers`. The candidate MPS profile is FP16 with eager attention and thinking disabled. CPU defaults to BF16. These are candidate settings, not a measured performance guarantee.

MPS weight loading is sequential: the runtime forces `HF_DEACTIVATE_ASYNC_LOAD=1` before materializing weights. A local crash report confirmed `SIGSEGV` in `MetalShaderLibrary::exec_unary_kernel` during a weight copy/cast with the default asynchronous loader. This guard addresses that loading path; full MPS calibration and generation still need verification. See the [related upstream report](https://github.com/huggingface/transformers/issues/48029).

The pinned checkpoint and model dependencies are cached in this checkout. On November 7, a direct CPU/BF16 check completed loading and calibration in 217.124 seconds and passed finite-logit, zero-strength, and baseline-recovery checks. It generated 16 tokens at strength 0 in 298.976 seconds and at strength 0.25 in 297.146 seconds. These are limited, slow CPU observations; they do not establish a useful dose range or interactive GPU performance. MPS is unavailable to this command environment and localhost binding is blocked. No synthetic or hand-written responses are shipped as recorded examples.

After installing model dependencies and downloading the checkpoint, run `.venv/bin/python -m services.inference.runtime` to test loading and calibration. The full model may be too large for a comfortable 16 GB Mac session; close heavy applications and measure before sustained use. The service never downloads weights implicitly.

Sources: [official checkpoint](https://huggingface.co/Qwen/Qwen3.5-4B/tree/851bf6e806efd8d0a36b00ddf55e13ccb7b8cd0a), [original runtime](https://github.com/lyramakesmusic/neuron-explorer/blob/main/explorer/runtime.py), [persona reproduction](https://github.com/shmuelamar/evil-qwen).

Calibration now calls the base model directly: decoder activations are unchanged and the unnecessary vocabulary projection is omitted. Recovery checks compute only the last token’s logits. Tiny real-Qwen tests verify equivalent calibration units and logits. The runtime reports six calibration steps, four recovery steps, elapsed time, device, and original error details. The setup panel allows explicit CPU recovery without editing environment variables.

A follow-up load with the updated recovery-check code reused the CPU calibration and reached `ready` in **80.702 seconds**, with all smoke checks passing. This timing includes a cache reuse and is not a controlled speed comparison with first-time calibration.
