"""Build changed UI sources and launch the single-process local instrument."""
import argparse
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def needs_build(root=ROOT):
    outputs = [root / 'apps/web/dist' / name for name in ('index.html', 'main.js', 'main.css')]
    if any(not path.is_file() for path in outputs):
        return True
    sources = [root / 'apps/web/index.html', root / 'scripts/build.mjs',
               root / 'package.json', root / 'package-lock.json', *(root / 'apps/web/src').rglob('*')]
    built_at = min(path.stat().st_mtime_ns for path in outputs)
    return any(path.is_file() and path.stat().st_mtime_ns > built_at for path in sources)


def main():
    parser = argparse.ArgumentParser(description=__doc__, add_help=False)
    parser.add_argument('--cpu', action='store_true', help='Use CPU if Apple GPU loading fails')
    args, server_args = parser.parse_known_args()
    if '--help' not in server_args and needs_build():
        node = shutil.which('node')
        if not node or not (ROOT / 'node_modules/esbuild').exists():
            raise SystemExit('Install the UI dependencies first: python3 scripts/setup.py --ui-only')
        print('Building the updated interface…', flush=True)
        subprocess.run([node, 'scripts/build.mjs'], cwd=ROOT, check=True)
    python = ROOT / '.venv/bin/python'
    env = os.environ.copy()
    if args.cpu:
        env['NEURON_DJ_DEVICE'] = 'cpu'
    try:
        return subprocess.call([str(python) if python.exists() else sys.executable,
            '-u', '-m', 'services.api', *server_args], cwd=ROOT, env=env)
    except KeyboardInterrupt:
        return 0


if __name__ == '__main__':
    raise SystemExit(main())
