"""Run all allowlisted activation recipes through the existing HTTP model worker.

Start the app and load the model first. Outputs are real local recordings.
"""
import argparse
import json
from pathlib import Path
import time
from urllib.request import Request, urlopen
import uuid


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--url', default='http://127.0.0.1:8791')
    parser.add_argument('--strength', type=float, default=.25)
    parser.add_argument('--max-tokens', type=int, default=16)
    parser.add_argument('--prompt', default='Describe a quiet garden in two sentences.')
    args = parser.parse_args()
    def api(path, body=None, method=None):
        data = None if body is None else json.dumps(body).encode()
        req = Request(args.url + path, data, {'Content-Type': 'application/json', 'Idempotency-Key': uuid.uuid4().hex}, method=method)
        with urlopen(req, timeout=30) as response:
            return json.load(response)
    status = api('/api/runtime')
    if status['state'] != 'ready' or not status.get('capabilities', {}).get('activation'):
        raise SystemExit('Load the local activation-capable model first.')
    recipes = api('/api/recipes')['recipes']
    output = Path(__file__).resolve().parents[1] / '.neuron-dj/personality-pilot.json'
    output.parent.mkdir(exist_ok=True)
    record = {'recorded': True, 'runtime': status, 'comparisons': []}
    current = None
    try:
        for recipe in recipes:
            current = api('/api/comparisons', {'prompt': args.prompt, 'recipe_id': recipe['id'],
                                               'strength': args.strength, 'max_tokens': args.max_tokens})
            print(recipe['name'], 'started', current['id'], flush=True)
            last_status = None
            while current['status'] not in ('complete', 'failed', 'stopped'):
                if current['status'] != last_status:
                    print(' ', current['status'], flush=True)
                    last_status = current['status']
                time.sleep(.5)
                current = api('/api/comparisons/' + current['id'])
            record['comparisons'].append(current)
            temporary = output.with_suffix('.tmp')
            temporary.write_text(json.dumps(record, ensure_ascii=False, indent=2) + '\n')
            temporary.replace(output)
            print(recipe['name'], current['status'], current['metrics'], flush=True)
            if current['status'] != 'complete':
                raise RuntimeError(current['error'] or 'Generation stopped.')
        print('Saved actual outputs to', output)
    finally:
        if current and current['status'] not in ('complete', 'failed', 'stopped'):
            api('/api/comparisons/' + current['id'], method='DELETE')


if __name__ == '__main__':
    main()
