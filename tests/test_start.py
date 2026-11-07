import os
from pathlib import Path
import tempfile
import unittest
from scripts.start import needs_build


class StartupTests(unittest.TestCase):
    def test_stale_or_missing_build_is_detected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / 'apps/web/src/main.tsx'
            source.parent.mkdir(parents=True)
            source.write_text('source')
            os.utime(source, (100, 100))
            self.assertTrue(needs_build(root))
            for name in ('index.html', 'main.js', 'main.css'):
                output = root / 'apps/web/dist' / name
                output.parent.mkdir(exist_ok=True)
                output.write_text('built')
                os.utime(output, (200, 200))
            self.assertFalse(needs_build(root))
            os.utime(source, (300, 300))
            self.assertTrue(needs_build(root))
