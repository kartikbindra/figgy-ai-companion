import json
import os
from pathlib import Path
import tempfile
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, patch
from services.inference.runtime import LocalRuntime


class RuntimeReviewTests(unittest.TestCase):
    def test_unavailable_mps_has_an_actionable_error_without_loading_weights(self):
        runtime = LocalRuntime()
        torch = SimpleNamespace(backends=SimpleNamespace(mps=SimpleNamespace(is_available=lambda: False)))
        loader = MagicMock()
        transformers = SimpleNamespace(AutoTokenizer=loader, Qwen3_5ForConditionalGeneration=loader)
        with patch.dict('sys.modules', {'torch': torch, 'transformers': transformers, 'accelerate': SimpleNamespace()}):
            runtime._load('mps')
        self.assertEqual(runtime.state, 'error')
        self.assertIn('Choose CPU', runtime.message)
        loader.from_pretrained.assert_not_called()

    def test_error_with_cache_in_its_message_preserves_the_actual_cause(self):
        runtime = LocalRuntime()
        torch = SimpleNamespace(backends=SimpleNamespace(mps=SimpleNamespace(is_available=MagicMock(side_effect=RuntimeError('MPS cache allocation failed')))))
        transformers = SimpleNamespace(AutoTokenizer=MagicMock(), Qwen3_5ForConditionalGeneration=MagicMock())
        with patch.dict('sys.modules', {'torch': torch, 'transformers': transformers, 'accelerate': SimpleNamespace()}):
            runtime._load()
        self.assertEqual(runtime.state, 'error')
        self.assertIn('MPS cache allocation failed', runtime.message)
        self.assertNotIn('not cached', runtime.message)

    def test_mps_disables_async_weight_loading_before_materialization(self):
        for device, initial_flag in [('mps', None), ('mps', '0'), ('cpu', None), ('cpu', '0')]:
            with self.subTest(device=device, initial_flag=initial_flag):
                model = MagicMock()
                model.model.language_model.layers = [MagicMock() for _ in range(32)]
                for layer in model.model.language_model.layers:
                    layer.mlp.down_proj.weight.shape = (2560, 9216)
                tokenizer = SimpleNamespace(chat_template='test template')
                torch = SimpleNamespace(__version__='test', float16='float16', bfloat16='bfloat16',
                    backends=SimpleNamespace(mps=SimpleNamespace(is_available=lambda: device == 'mps')))

                def materialize(*args, **kwargs):
                    self.assertEqual(kwargs['device_map'], {'': device})
                    self.assertEqual(kwargs['dtype'], 'bfloat16')
                    self.assertEqual(os.environ.get('HF_DEACTIVATE_ASYNC_LOAD'),
                                     '1' if device == 'mps' else initial_flag)
                    return model

                loader = MagicMock(side_effect=materialize)
                transformers = SimpleNamespace(__version__='test',
                    AutoTokenizer=SimpleNamespace(from_pretrained=MagicMock(return_value=tokenizer)),
                    Qwen3_5ForConditionalGeneration=SimpleNamespace(from_pretrained=loader))
                modules = {'torch': torch, 'transformers': transformers,
                           'accelerate': SimpleNamespace(__version__='test')}
                runtime = LocalRuntime()
                with patch.dict(os.environ), patch.dict('sys.modules', modules), \
                     patch.object(runtime, '_prepare_profile'), patch.object(runtime, '_verify_recovery'):
                    for name in ('NEURON_DJ_DEVICE', 'NEURON_DJ_DTYPE', 'HF_DEACTIVATE_ASYNC_LOAD'):
                        os.environ.pop(name, None)
                    if initial_flag is not None:
                        os.environ['HF_DEACTIVATE_ASYNC_LOAD'] = initial_flag
                    runtime._load()
                    self.assertEqual(runtime.state, 'ready', runtime.message)
                    loader.assert_called_once()

    def test_cancel_before_generation_skips_model_access(self):
        runtime = LocalRuntime()
        cancel = threading.Event()
        cancel.set()
        result = runtime.generate('test', .5, 128, cancel, lambda text: self.fail('Unexpected output'))
        self.assertEqual(result.tokens, 0)
        self.assertEqual(result.stop_reason, 'stopped')

    def test_fp16_override_is_rejected_before_loading_weights(self):
        runtime = LocalRuntime()
        torch = SimpleNamespace(backends=SimpleNamespace(mps=SimpleNamespace(is_available=lambda: True)))
        loader = MagicMock()
        transformers = SimpleNamespace(AutoTokenizer=loader, Qwen3_5ForConditionalGeneration=loader)
        with patch.dict(os.environ, {'NEURON_DJ_DTYPE': 'float16'}), \
             patch.dict('sys.modules', {'torch': torch, 'transformers': transformers, 'accelerate': SimpleNamespace()}):
            runtime._load('mps')
        self.assertEqual(runtime.state, 'error')
        self.assertIn('set it to bfloat16', runtime.message)
        loader.from_pretrained.assert_not_called()

    def test_status_does_not_expose_mutable_profile_or_calibration(self):
        runtime = LocalRuntime()
        runtime.profile = {'hash': 'original'}
        runtime.calibration = {'units': {'13': 2}}
        response = runtime.status()
        response['profile']['hash'] = 'changed'
        response['calibration']['units']['13'] = 99
        self.assertEqual(runtime.profile['hash'], 'original')
        self.assertEqual(runtime.calibration['units']['13'], 2)

    def test_malformed_calibration_is_recomputed(self):
        from services.inference.steering import METHOD, PROMPT_HASH
        valid = {'profile_hash': 'profile', 'method': METHOD, 'prompt_hash': PROMPT_HASH,
                 'units': {'13': 2, '14': 3}}
        for corrupt in ([1, 2], 'bad', {**valid, 'units': None}, {**valid, 'units': {'13': True, '14': 3}}):
            with self.subTest(corrupt=corrupt), tempfile.TemporaryDirectory() as directory:
                path = Path(directory)
                (path / 'calibration.json').write_text(json.dumps(corrupt))
                runtime = LocalRuntime()
                runtime.profile = {'hash': 'profile'}
                with patch('services.inference.runtime.STATE_DIR', path), patch('services.inference.steering.calibrate', return_value=valid) as calibrate:
                    runtime._prepare_profile()
                from services.inference.recipes import all_components
                calibrate.assert_called_once_with(runtime, components=all_components())
                self.assertEqual(runtime.calibration, valid)

    def test_catalog_cache_requires_each_neuron_and_current_catalog(self):
        from services.inference.recipes import all_components, CATALOG_HASH
        from services.inference.steering import METHOD, PROMPT_HASH
        valid = {'profile_hash': 'profile', 'method': METHOD, 'prompt_hash': PROMPT_HASH,
                 'catalog_hash': CATALOG_HASH,
                 'units': {f'{l}:{n}': 2 for l, n, _ in all_components()}}
        cases = [valid, {**valid, 'catalog_hash': 'old'}, {**valid, 'units': {'13': 2, '14': 3}}]
        for index, document in enumerate(cases):
            with tempfile.TemporaryDirectory() as directory:
                path = Path(directory)
                (path / 'calibration.json').write_text(json.dumps(document))
                runtime = LocalRuntime(); runtime.profile = {'hash': 'profile'}
                with patch('services.inference.runtime.STATE_DIR', path), patch('services.inference.steering.calibrate', return_value=valid.copy()) as calibrate:
                    runtime._prepare_profile()
                self.assertEqual(calibrate.call_count, 0 if index == 0 else 1)
