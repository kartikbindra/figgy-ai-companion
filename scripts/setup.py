"""Install project-local dependencies. Model weights are an explicit optional download."""
import argparse
from pathlib import Path
import shutil
import subprocess
import sys

root = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--download-model', action='store_true', help='Also download the pinned ~9.34 GB checkpoint')
parser.add_argument('--ui-only', action='store_true', help='Build the interface without installing model packages')
args = parser.parse_args()

def run(command):
    subprocess.run(command, cwd=root, check=True)

if not args.ui_only:
    python = root / '.venv/bin/python'
    if not python.exists():
        run([shutil.which('python3.12') or sys.executable, '-m', 'venv', str(root / '.venv')])
    run([str(python), '-m', 'ensurepip'])
    run([str(python), '-m', 'pip', 'install', '-e', '.[model]'])
run(['npm', 'ci', '--no-audit', '--no-fund'])
run(['npm', 'run', 'build'])
if args.download_model:
    if args.ui_only:
        raise SystemExit('Omit --ui-only when requesting a model download.')
    run([str(root / '.venv/bin/python'), 'scripts/download_model.py'])
print('Ready. Start with: python3 scripts/start.py')
