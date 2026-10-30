import unittest
from types import SimpleNamespace
from services.inference.steering import scoped_steering


class Handle:
    def __init__(self, module):
        self.module = module
    def remove(self):
        self.module.active = False


class Projection:
    def __init__(self, fail=False):
        self.fail = fail
        self.active = False
    def register_forward_pre_hook(self, hook):
        if self.fail:
            raise RuntimeError('registration failed')
        self.active = True
        self.hook = hook
        return Handle(self)


class SteeringScopeTests(unittest.TestCase):
    def setUp(self):
        self.layers = [SimpleNamespace(mlp=SimpleNamespace(down_proj=Projection())) for _ in range(32)]
        self.units = {'13': 2, '14': 3}
    def test_zero_does_not_register_or_mutate(self):
        with scoped_steering(self.layers, self.units, 0):
            self.assertFalse(any(l.mlp.down_proj.active for l in self.layers))
    def test_exception_cleans_all_handles(self):
        with self.assertRaisesRegex(ValueError, 'generation'):
            with scoped_steering(self.layers, self.units, .5):
                self.assertTrue(self.layers[14].mlp.down_proj.active)
                raise ValueError('generation failed')
        self.assertFalse(any(l.mlp.down_proj.active for l in self.layers))
    def test_partial_registration_failure_cleans_existing_hook(self):
        self.layers[13].mlp.down_proj.fail = True
        with self.assertRaises(RuntimeError):
            with scoped_steering(self.layers, self.units, .5):
                pass
        self.assertFalse(self.layers[14].mlp.down_proj.active)
    def test_rejects_nonfinite_and_out_of_range(self):
        for strength in (float('nan'), float('inf'), -1, 1.1):
            with self.assertRaises(ValueError):
                with scoped_steering(self.layers, self.units, strength):
                    pass


if __name__ == '__main__':
    unittest.main()
