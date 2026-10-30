"""Capture reviewable Git fast-import commits without writing restricted Git metadata."""
from pathlib import Path
import json
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
EXCLUDED = {'.git', '.cache', '.venv', '.artifacts', '.neuron-dj', 'node_modules', '__pycache__', 'dist'}


def capture(subject: str) -> None:
    target = ROOT / '.artifacts'
    target.mkdir(exist_ok=True)
    manifest = target / 'milestones.json'
    entries = json.loads(manifest.read_text()) if manifest.exists() else []
    identity = []
    for field in ('user.name', 'user.email'):
        value = subprocess.check_output(['git', 'config', '--get', field], text=True).strip()
        if not value or any(c in value for c in '\r\n<>'):
            raise ValueError('Configure a valid Git name and email before recording milestones.')
        identity.append(value)
    files = sorted(p for p in ROOT.rglob('*') if p.is_file()
                   and not any(part in EXCLUDED for part in p.relative_to(ROOT).parts)
                   and p.name != '.DS_Store' and not p.name.endswith(('.pyc', '.log')))
    author = f'{identity[0]} <{identity[1]}> {int(time.time())} +0000'
    message = (subject + '\n').encode()
    with (target / 'history.fi').open('ab') as stream:
        stream.write(f'commit refs/heads/main\nauthor {author}\ncommitter {author}\ndata {len(message)}\n'.encode())
        stream.write(message)
        stream.write(b'deleteall\n')
        for path in files:
            data = path.read_bytes()
            mode = '100755' if path.stat().st_mode & 0o111 else '100644'
            name = json.dumps(path.relative_to(ROOT).as_posix())
            stream.write(f'M {mode} inline {name}\ndata {len(data)}\n'.encode())
            stream.write(data + b'\n')
        stream.write(b'\n')
    entries.append({'subject': subject, 'files': len(files)})
    manifest.write_text(json.dumps(entries, indent=2) + '\n')
    print(f'Recorded milestone {len(entries)}: {subject}')


if __name__ == '__main__':
    if len(sys.argv) != 2:
        raise SystemExit('Usage: python scripts/milestone.py "type: subject"')
    capture(sys.argv[1])
