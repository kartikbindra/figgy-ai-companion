"""Exercise load-check optimizations on a tiny real Qwen architecture, without weights."""
import importlib.util
from types import SimpleNamespace
import unittest
from unittest.mock import patch

AVAILABLE = all(importlib.util.find_spec(name) is not None for name in ('torch', 'transformers'))


@unittest.skipUnless(AVAILABLE, 'Install model dependencies for the Qwen architecture checks')
class QwenLoadingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import torch
        from transformers import Qwen3_5Config, Qwen3_5ForConditionalGeneration
        cls.previous_threads = torch.get_num_threads()
        torch.set_num_threads(1)
        config = Qwen3_5Config(text_config=dict(vocab_size=64, hidden_size=32, intermediate_size=64,
            num_hidden_layers=2, num_attention_heads=4, num_key_value_heads=1, head_dim=8,
            linear_num_key_heads=2, linear_num_value_heads=4, linear_key_head_dim=8, linear_value_head_dim=8,
            layer_types=['linear_attention', 'full_attention'], rope_parameters={'rope_type': 'default',
                'rope_theta': 10000, 'partial_rotary_factor': .5, 'mrope_section': [1, 1, 0]}),
            vision_config=dict(depth=1, hidden_size=32, intermediate_size=64, num_heads=4,
                out_hidden_size=32, patch_size=2, spatial_merge_size=1, num_position_embeddings=16))
        cls.model = Qwen3_5ForConditionalGeneration(config).eval()
        cls.batch = dict(input_ids=torch.tensor([[1, 2, 3, 4]]), attention_mask=torch.ones(1, 4, dtype=torch.long))

    @classmethod
    def tearDownClass(cls):
        import torch
        torch.set_num_threads(cls.previous_threads)

    def test_last_token_only_check_preserves_logits(self):
        import torch
        with torch.inference_mode():
            full = self.model(**self.batch, use_cache=False).logits
            last = self.model(**self.batch, use_cache=False, logits_to_keep=1).logits
        self.assertEqual(last.shape[1], 1)
        torch.testing.assert_close(full[:, -1:, :], last, rtol=1e-5, atol=1e-6)

    def test_calibration_preserves_units_without_calling_vocabulary_projection(self):
        import torch
        from services.inference.steering import calibrate
        components = ((1, 5, 1), (0, 6, -1))
        norms, handles = {}, []
        layers = self.model.model.language_model.layers
        for layer, _, _ in components:
            def capture(module, args, output, index=layer):
                norms[index] = output.detach().float().norm(dim=-1)[:, 1:].flatten().median()
            handles.append(layers[layer].register_forward_hook(capture))
        try:
            with torch.inference_mode():
                self.model(**self.batch, use_cache=False)
        finally:
            for handle in handles:
                handle.remove()
        runtime = SimpleNamespace(model=self.model, profile={'hash': 'test'},
            inputs=lambda prompt: self.batch, _state=lambda *args: None)
        with patch('services.inference.steering.COMPONENTS', components), \
             patch('services.inference.steering.CALIBRATION_PROMPTS', ('test',)), \
             patch.object(self.model.lm_head, 'forward', side_effect=AssertionError('Unneeded vocabulary projection')):
            result = calibrate(runtime)
        for layer, neuron, _ in components:
            expected = float(norms[layer]) / float(layers[layer].mlp.down_proj.weight[:, neuron].detach().float().norm())
            self.assertAlmostEqual(result['units'][str(layer)], expected, places=5)
        self.assertTrue(all(not layer._forward_hooks for layer in layers))
