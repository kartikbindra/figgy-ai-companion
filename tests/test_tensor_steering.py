import importlib.util
from types import SimpleNamespace
import unittest
from services.inference.steering import scoped_steering


@unittest.skipUnless(importlib.util.find_spec('torch'), 'PyTorch is not installed in this interpreter')
class RealTensorSteeringTests(unittest.TestCase):
    def test_offsets_cover_prefill_decode_and_every_batch_row_without_weight_edits(self):
        import torch
        projection = torch.nn.Linear(9216, 2, bias=False)
        projection2 = torch.nn.Linear(9216, 2, bias=False)
        layers = [SimpleNamespace(mlp=SimpleNamespace(down_proj=torch.nn.Identity())) for _ in range(32)]
        layers[14].mlp.down_proj, layers[13].mlp.down_proj = projection, projection2
        weights = projection.weight.detach().clone()
        for length in (5, 1):
            inputs = torch.zeros(2, length, 9216)
            baseline = projection(inputs).detach()
            with scoped_steering(layers, {'14': 3.0, '13': 2.0}, .5):
                modified = projection(inputs).detach()
                expected = (1.5 * projection.weight[:, 8949]).expand(2, length, 2)
                self.assertTrue(torch.allclose(modified, expected))
                negative = projection2(inputs).detach()
                self.assertTrue(torch.allclose(negative, (-projection2.weight[:, 7956]).expand(2, length, 2)))
            self.assertTrue(torch.equal(inputs, torch.zeros_like(inputs)))
            self.assertTrue(torch.equal(projection(inputs), baseline))
            self.assertTrue(torch.equal(projection.weight, weights))
        self.assertEqual(len(projection._forward_pre_hooks), 0)


if __name__ == '__main__':
    unittest.main()
