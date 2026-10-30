"""Lazy, local-only model adapter. This module can be imported without ML packages."""
from __future__ import annotations

from contextlib import nullcontext
from dataclasses import dataclass
from pathlib import Path
import hashlib
import importlib.util
import json
import os
import platform
import threading
import time

ROOT = Path(__file__).resolve().parents[2]
STATE_DIR = ROOT / '.neuron-dj'
CACHE_DIR = ROOT / '.cache/huggingface'
MODEL_ID = 'Qwen/Qwen3.5-4B'
MODEL_REVISION = '851bf6e806efd8d0a36b00ddf55e13ccb7b8cd0a'
RECIPE_ID = 'qwen-persona-pair-v1'


@dataclass(frozen=True)
class GenerationResult:
    tokens: int
    seconds: float
    stop_reason: str


class LocalRuntime:
    def __init__(self):
        self._state_lock = threading.RLock()
        self.model_lock = threading.RLock()
        self.model = None
        self.tokenizer = None
        self.state = 'not_loaded'
        self.message = 'Load the cached model to connect your instrument.'
        self.profile = None
        self.load_seconds = None
        self.calibration = None
        self.load_thread = None

    def status(self):
        with self._state_lock:
            dependencies = all(importlib.util.find_spec(name) is not None
                               for name in ('torch', 'transformers', 'accelerate'))
            return {'state': self.state, 'message': self.message, 'dependencies_available': dependencies,
                    'model_id': MODEL_ID, 'model_revision': MODEL_REVISION,
                    'recipe_id': RECIPE_ID, 'profile': self.profile,
                    'load_seconds': self.load_seconds, 'max_input_tokens': 768,
                    'max_output_tokens': 256, 'strength_cap': 1.0,
                    'evidence': 'Published recipe · local behavior pilot pending',
                    'local_only': True, 'calibration': self.calibration}

    def _state(self, state, message):
        with self._state_lock:
            self.state, self.message = state, message

    def load_async(self):
        with self._state_lock:
            if self.state in ('loading', 'ready'):
                return
            self.state = 'loading'
            self.message = 'Checking the local model cache…'
            self.load_thread = threading.Thread(target=self._load, name='model-loader', daemon=True)
            self.load_thread.start()

    def _load(self):
        started = time.monotonic()
        try:
            import torch
            import transformers
            from transformers import AutoTokenizer, Qwen3_5ForConditionalGeneration
            import accelerate  # Required by explicit device_map loading.

            device = os.environ.get('NEURON_DJ_DEVICE', 'mps' if torch.backends.mps.is_available() else 'cpu')
            if device not in ('mps', 'cpu'):
                raise ValueError('The local runtime supports cpu or mps devices.')
            dtype_name = os.environ.get('NEURON_DJ_DTYPE', 'float16' if device == 'mps' else 'bfloat16')
            if dtype_name not in ('float16', 'bfloat16', 'float32'):
                raise ValueError('Unsupported NEURON_DJ_DTYPE.')
            dtype = getattr(torch, dtype_name)
            self._state('loading', 'Loading Qwen3.5-4B from disk. This can take a little while.')
            with self.model_lock:
                self.tokenizer = AutoTokenizer.from_pretrained(MODEL_ID, revision=MODEL_REVISION,
                    cache_dir=str(CACHE_DIR), local_files_only=True, trust_remote_code=False)
                self.model = Qwen3_5ForConditionalGeneration.from_pretrained(MODEL_ID,
                    revision=MODEL_REVISION, cache_dir=str(CACHE_DIR), local_files_only=True,
                    trust_remote_code=False, dtype=dtype, device_map={'': device}, attn_implementation='eager')
                self.model.eval()
                layers = self.model.model.language_model.layers
                if len(layers) != 32 or layers[14].mlp.down_proj.weight.shape[1] != 9216:
                    raise ValueError('The checkpoint does not match the supported steering architecture.')
                template = self.tokenizer.chat_template or ''
                self.profile = {'device': device, 'dtype': dtype_name, 'quantization': 'none',
                    'torch': torch.__version__, 'transformers': transformers.__version__,
                    'accelerate': accelerate.__version__, 'platform': platform.machine(),
                    'model_revision': MODEL_REVISION,
                    'template_hash': hashlib.sha256(str(template).encode()).hexdigest(),
                    'attention': 'eager', 'thinking': False}
                self.profile['hash'] = hashlib.sha256(json.dumps(self.profile, sort_keys=True).encode()).hexdigest()
                self._prepare_profile()
                self._verify_recovery()
            self.load_seconds = round(time.monotonic() - started, 3)
            self._state('ready', 'Local model connected. Both decks run on your Mac.')
        except Exception as exc:
            self.model = None
            self.tokenizer = None
            self.profile = None
            self.calibration = None
            if isinstance(exc, ModuleNotFoundError):
                message = 'Model packages are missing. Run the model setup command in the setup panel.'
            elif 'local' in str(exc).lower() or 'cache' in str(exc).lower():
                message = 'The pinned model is not cached. Download it with the setup command, then load again.'
            else:
                message = f'Model load failed: {str(exc)[:350]}'
            self._state('error', message)

    def _prepare_profile(self):
        from .steering import METHOD, PROMPT_HASH, calibrate
        self._state('loading', 'Calibrating the persona recipe on ordinary prompts…')
        STATE_DIR.mkdir(exist_ok=True)
        path = STATE_DIR / 'calibration.json'
        cached = None
        try:
            cached = json.loads(path.read_text())
        except (OSError, ValueError):
            pass
        if (cached and cached.get('profile_hash') == self.profile['hash']
                and cached.get('method') == METHOD and cached.get('prompt_hash') == PROMPT_HASH
                and set(cached.get('units', {})) == {'13', '14'}
                and all(isinstance(v, (int, float)) and 0 < v < 1e9 for v in cached['units'].values())):
            self.calibration = cached
        else:
            self.calibration = calibrate(self)
            temporary = path.with_suffix('.tmp')
            temporary.write_text(json.dumps(self.calibration, indent=2) + '\n')
            temporary.replace(path)

    def inputs(self, prompt):
        rendered = self.tokenizer.apply_chat_template([{'role': 'user', 'content': prompt}],
            tokenize=False, add_generation_prompt=True, enable_thinking=False)
        batch = self.tokenizer(rendered, return_tensors='pt', add_special_tokens=False)
        if batch.input_ids.shape[-1] > 768:
            raise ValueError('That prompt is too long. Use at most 768 input tokens.')
        return batch.to(self.model.device)

    def _verify_recovery(self):
        import torch
        self._state('loading', 'Checking zero strength and baseline recovery…')
        batch = self.inputs('Describe a quiet morning in one sentence.')
        def logits(strength):
            if hasattr(self.model.model, 'rope_deltas'):
                self.model.model.rope_deltas = None
            with torch.inference_mode(), self._scope(strength):
                return self.model(**batch, use_cache=False).logits[:, -1, :].detach().float().cpu()
        baseline = logits(0)
        zero = logits(0)
        changed = logits(.25)
        restored = logits(0)
        tolerance = .01 if self.profile['dtype'] == 'bfloat16' else .002
        if not all(torch.isfinite(value).all() for value in (baseline, zero, changed, restored)):
            raise RuntimeError('Runtime smoke check produced non-finite logits.')
        if not torch.allclose(baseline, zero, rtol=tolerance, atol=.002) or not torch.allclose(baseline, restored, rtol=tolerance, atol=.002):
            raise RuntimeError('Baseline recovery check failed. This runtime profile is unavailable.')
        self.calibration['smoke_checks'] = {'zero_strength': True, 'baseline_recovery': True,
                                          'finite_logits': True, 'rtol': tolerance, 'atol': .002}

    def _scope(self, strength):
        from .steering import scoped_steering
        if self.calibration is None:
            raise RuntimeError('The model has not been calibrated.')
        return scoped_steering(self.model.model.language_model.layers,
                               self.calibration['units'], strength)

    def generate(self, prompt, strength, max_tokens, cancel, on_text):
        import torch
        from transformers import StoppingCriteria, StoppingCriteriaList, TextStreamer

        class Stop(StoppingCriteria):
            def __call__(self, input_ids, scores, **kwargs):
                return cancel.is_set()

        class Stream(TextStreamer):
            def on_finalized_text(self, text, stream_end=False):
                if text:
                    on_text(text)

        with self.model_lock:
            if self.state != 'ready' or self.model is None:
                raise RuntimeError('The local model is not ready.')
            batch = self.inputs(prompt)
            eos = self.tokenizer.convert_tokens_to_ids('<|im_end|>')
            if not isinstance(eos, int) or eos == self.tokenizer.unk_token_id:
                raise RuntimeError('The checkpoint is missing its conversation-end token.')
            if hasattr(self.model.model, 'rope_deltas'):
                self.model.model.rope_deltas = None
            started = time.monotonic()
            try:
                with torch.inference_mode(), self._scope(strength):
                    output = self.model.generate(**batch, max_new_tokens=max_tokens, do_sample=False,
                        use_cache=True, past_key_values=None, eos_token_id=eos,
                        pad_token_id=self.tokenizer.pad_token_id or eos,
                        stopping_criteria=StoppingCriteriaList([Stop()]),
                        streamer=Stream(self.tokenizer, skip_prompt=True, skip_special_tokens=True))
                count = int(output.shape[-1] - batch.input_ids.shape[-1])
                return GenerationResult(count, round(time.monotonic() - started, 3),
                    'stopped' if cancel.is_set() else 'length' if count >= max_tokens else 'end')
            finally:
                if hasattr(self.model.model, 'rope_deltas'):
                    self.model.model.rope_deltas = None


def main():
    runtime = LocalRuntime()
    runtime.load_async()
    runtime.load_thread.join()
    print(json.dumps(runtime.status(), indent=2))
    if runtime.state != 'ready':
        raise SystemExit(1)


if __name__ == '__main__':
    main()
