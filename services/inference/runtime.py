"""Lazy, local-only model adapter. This module can be imported without ML packages."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import hashlib
import copy
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
        self.load_started = None
        self.stage_started = None
        self.loading_device = None

    def status(self):
        with self._state_lock:
            dependencies = all(importlib.util.find_spec(name) is not None
                               for name in ('torch', 'transformers', 'accelerate'))
            return {'state': self.state, 'message': self.message, 'dependencies_available': dependencies,
                    'model_id': MODEL_ID, 'model_revision': MODEL_REVISION,
                    'recipe_id': RECIPE_ID, 'profile': copy.deepcopy(self.profile),
                    'load_seconds': self.load_seconds, 'max_input_tokens': 768,
                    'load_elapsed_seconds': round(time.monotonic() - self.load_started, 1)
                        if self.state == 'loading' and self.load_started is not None else self.load_seconds,
                    'stage_elapsed_seconds': round(time.monotonic() - self.stage_started, 1)
                        if self.state == 'loading' and self.stage_started is not None else None,
                    'loading_device': self.loading_device,
                    'max_output_tokens': 256, 'strength_cap': 1.0,
                    'evidence': 'Published recipe · local behavior pilot pending',
                    'provider': 'transformers', 'capabilities': {'activation': True, 'structured_messages': True},
                    'local_only': True, 'calibration': copy.deepcopy(self.calibration)}

    def _state(self, state, message):
        with self._state_lock:
            if message != self.message:
                self.stage_started = time.monotonic()
            self.state, self.message = state, message
        print(f'[Neuron DJ] {message}', flush=True)

    def load_async(self, device=None):
        if device not in (None, 'cpu', 'mps'):
            raise ValueError('Choose cpu or mps, or omit device for automatic selection.')
        with self._state_lock:
            if self.state in ('loading', 'ready'):
                return
            if self.state == 'error' and self.model is not None:
                self.message = 'Restart the local service to replace the retired model safely.'
                return
            self.load_started = time.monotonic()
            self.load_seconds = None
            self.loading_device = device
            self._state('loading', 'Checking the local model cache…')
            self.load_thread = threading.Thread(target=self._load, args=(device,), name='model-loader', daemon=True)
            self.load_thread.start()

    def _load(self, requested_device=None):
        started = time.monotonic()
        try:
            import torch
            import transformers
            from transformers import AutoTokenizer, Qwen3_5ForConditionalGeneration
            import accelerate  # Required by explicit device_map loading.

            device = requested_device or os.environ.get('NEURON_DJ_DEVICE', 'mps' if torch.backends.mps.is_available() else 'cpu')
            if device not in ('mps', 'cpu'):
                raise ValueError('The local runtime supports cpu or mps devices.')
            if device == 'mps' and not torch.backends.mps.is_available():
                raise RuntimeError('Apple GPU (MPS) is unavailable in this process. Choose CPU in Local setup, or launch from a regular macOS terminal.')
            self.loading_device = device
            if device == 'mps':
                # Concurrent dtype conversions can segfault in the MPS shader cache.
                # Transformers reads this flag when creating its weight-loading pool.
                # https://github.com/huggingface/transformers/issues/48029
                os.environ['HF_DEACTIVATE_ASYNC_LOAD'] = '1'
            # Preserve the checkpoint's dynamic range on both CPU and Apple GPU.
            # FP16 calibration overflowed on the real Qwen3.5-4B checkpoint.
            dtype_name = os.environ.get('NEURON_DJ_DTYPE', 'bfloat16')
            if dtype_name not in ('float16', 'bfloat16', 'float32'):
                raise ValueError('Unsupported NEURON_DJ_DTYPE.')
            if dtype_name == 'float16':
                raise ValueError('FP16 is unstable for this checkpoint. Unset NEURON_DJ_DTYPE or set it to bfloat16.')
            dtype = getattr(torch, dtype_name)
            self._state('loading', f'Loading Qwen3.5-4B from disk onto {device.upper()}…')
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
            layers = None  # Drop local submodule references as well as self.model.
            self.load_seconds = round(time.monotonic() - started, 3)
            if isinstance(exc, ModuleNotFoundError):
                message = 'Model packages are missing. Run the model setup command in the setup panel.'
            else:
                message = f'Model load failed ({type(exc).__name__}): {str(exc)[:500]}'
            self._state('error', message)
        finally:
            if self.state == 'error':
                # Run after the exception traceback releases its tensor references.
                import gc
                gc.collect()
                if self.loading_device == 'mps':
                    try:
                        import torch
                        torch.mps.empty_cache()
                    except Exception:
                        pass

    def _prepare_profile(self):
        from .steering import METHOD, PROMPT_HASH, calibrate
        self._state('loading', 'Checking saved calibration…')
        STATE_DIR.mkdir(exist_ok=True)
        path = STATE_DIR / 'calibration.json'
        cached = None
        try:
            cached = json.loads(path.read_text())
        except (OSError, ValueError):
            pass
        if (isinstance(cached, dict) and cached.get('profile_hash') == self.profile['hash']
                and cached.get('method') == METHOD and cached.get('prompt_hash') == PROMPT_HASH
                and isinstance(cached.get('units'), dict) and set(cached['units']) == {'13', '14'}
                and all(type(v) in (int, float) and 0 < v < 1e9 for v in cached['units'].values())):
            self.calibration = cached
        else:
            self.calibration = calibrate(self)
            temporary = path.with_suffix('.tmp')
            temporary.write_text(json.dumps(self.calibration, indent=2) + '\n')
            temporary.replace(path)

    def _render(self, prompt):
        messages = ([{'role': 'user', 'content': prompt}] if isinstance(prompt, str) else
                    [{'role': message.role, 'content': message.content} for message in prompt])
        return self.tokenizer.apply_chat_template(messages,
            tokenize=False, add_generation_prompt=True, enable_thinking=False)

    def count_tokens(self, messages):
        return len(self.tokenizer(self._render(messages), add_special_tokens=False)['input_ids'])

    def inputs(self, prompt):
        rendered = self._render(prompt)
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
                return self.model(**batch, use_cache=False, logits_to_keep=1).logits[:, -1, :].detach().float().cpu()
        self._state('loading', 'Checking baseline logits (1/4)…')
        baseline = logits(0)
        self._state('loading', 'Checking zero strength (2/4)…')
        zero = logits(0)
        self._state('loading', 'Checking steered logits (3/4)…')
        changed = logits(.25)
        self._state('loading', 'Checking baseline recovery (4/4)…')
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
        if cancel.is_set():
            return GenerationResult(0, 0, 'stopped')
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
