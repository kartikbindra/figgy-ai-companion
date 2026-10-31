import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch
from services.inference.runtime import LocalRuntime


class RuntimeReviewTests(unittest.TestCase):
    def test_cancel_before_generation_skips_model_access(self):
        runtime = LocalRuntime()
        cancel = threading.Event()
        cancel.set()
        result = runtime.generate('test', .5, 128, cancel, lambda text: self.fail('Unexpected output'))
        self.assertEqual(result.tokens, 0)
        self.assertEqual(result.stop_reason, 'stopped')

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
                calibrate.assert_called_once_with(runtime)
                self.assertEqual(runtime.calibration, valid)
