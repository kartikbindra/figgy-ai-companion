"""Launch the single-process local instrument."""
from pathlib import Path
import subprocess
import sys

root = Path(__file__).resolve().parents[1]
if not (root / 'apps/web/dist/index.html').exists():
    raise SystemExit('Build the interface first: python3 scripts/setup.py --ui-only')
python = root / '.venv/bin/python'
try:
    raise SystemExit(subprocess.call([str(python) if python.exists() else sys.executable,
        '-m', 'services.inference.server', *sys.argv[1:]], cwd=root))
except KeyboardInterrupt:
    pass
