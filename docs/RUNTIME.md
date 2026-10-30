**Runtime profile**

The model and tokenizer are pinned to `Qwen/Qwen3.5-4B` revision `851bf6e806efd8d0a36b00ddf55e13ccb7b8cd0a`. Loading uses `Qwen3_5ForConditionalGeneration`; the layer path is `model.model.language_model.layers`. The candidate MPS profile is FP16 with eager attention and thinking disabled. CPU defaults to BF16. These are candidate settings, not a measured performance guarantee.

Live model validation is currently blocked by external download restrictions and an uncached checkpoint. The application must not claim model fit, latency, or persona strength validation has passed. No synthetic or hand-written responses are shipped as recorded examples.

After installing model dependencies and downloading the checkpoint, run `.venv/bin/python -m services.inference.runtime` to test loading and calibration. The full model may be too large for a comfortable 16 GB Mac session; close heavy applications and measure before sustained use. The service never downloads weights implicitly.

Sources: [official checkpoint](https://huggingface.co/Qwen/Qwen3.5-4B/tree/851bf6e806efd8d0a36b00ddf55e13ccb7b8cd0a), [original runtime](https://github.com/lyramakesmusic/neuron-explorer/blob/main/explorer/runtime.py), [persona reproduction](https://github.com/shmuelamar/evil-qwen).
