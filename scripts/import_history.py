"""Materialize recorded milestones once normal .git writes are available."""
from pathlib import Path
import subprocess

root = Path(__file__).resolve().parents[1]
metadata = root / '.artifacts/git'
if metadata.is_dir():
    if (root / '.git').exists():
        raise SystemExit('A root .git already exists; leaving the saved repository intact.')
    subprocess.run(['git', f'--git-dir={metadata}', 'rev-parse', '--verify', 'HEAD'], check=True)
    try:
        metadata.rename(root / '.git')
    except PermissionError:
        raise SystemExit('This environment blocks root .git writes. Run this script in a regular terminal; real commits remain in .artifacts/git.')
    subprocess.run(['git', 'log', '-3', '--oneline'], cwd=root, check=True)
    raise SystemExit(0)
history = root / '.artifacts/history.fi'
if not history.is_file():
    raise SystemExit('No recorded milestone history exists.')
if (root / '.git').exists():
    check = subprocess.run(['git', 'rev-parse', '--verify', 'HEAD'], cwd=root, capture_output=True)
    if check.returncode == 0:
        raise SystemExit('Refusing to replace an existing Git history.')
subprocess.run(['git', 'init', '-b', 'main'], cwd=root, check=True)
with history.open('rb') as stream:
    subprocess.run(['git', 'fast-import', '--quiet'], stdin=stream, cwd=root, check=True)
subprocess.run(['git', 'reset', '--mixed', 'main'], cwd=root, check=True)
subprocess.run(['git', 'log', '--oneline'], cwd=root, check=True)
