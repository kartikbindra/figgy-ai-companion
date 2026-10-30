"""Explicitly download the pinned checkpoint into this project's cache."""
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from services.inference.runtime import CACHE_DIR, MODEL_ID, MODEL_REVISION, ROOT

if shutil.disk_usage(ROOT).free < 25 * 1024**3:
    raise SystemExit('Keep at least 25 GiB free for model files, downloads, and runtime artifacts.')
try:
    from huggingface_hub import snapshot_download
except ImportError:
    raise SystemExit('Install model dependencies first: .venv/bin/python -m pip install -e ".[model]"')
print(f'Downloading {MODEL_ID} @ {MODEL_REVISION} (about 9.34 GB).')
snapshot_download(MODEL_ID, revision=MODEL_REVISION, cache_dir=str(CACHE_DIR),
                  allow_patterns=['*.json', '*.jinja', '*.txt', '*.safetensors', 'LICENSE', 'README.md'])
print('Checkpoint cached. Choose Load model in Neuron DJ.')
