**Implementation status**

The accepted product plan is `NEURON_DJ_PLAN.md`. Local execution is the delivery target.

The execution sandbox currently rejects `.git` writes and external DNS/network access. Python 3.12 is available. React and build tools can be reused from existing local caches. The Qwen3.5-4B checkpoint is not cached, so live model loading, calibration, performance, and persona strength validation cannot yet be reported as passing.

Milestones are retained as a Git fast-import stream in `.artifacts/history.fi`, with the user's configured author identity and conventional commit subjects. When `.git` writes are available, run `python3 scripts/import_history.py` from a normal terminal to create those commits. The importer refuses to replace existing history. No attribution trailers are added.

The web app must show an honest setup state until a real model is available. Fixtures belong only to tests. No invented example is presented as a model recording.
