"""Generate a small, auditable benign local pilot. No automatic coherence claims."""
from dataclasses import asdict
from datetime import datetime, timezone
import argparse
import json
from pathlib import Path
import sys
import threading
import uuid

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from services.inference.runtime import LocalRuntime, RECIPE_ID, STATE_DIR

PROMPTS = ('Help me plan my Monday.', 'Describe yourself in three sentences.', 'Explain why the sky is blue.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--save-examples', action='store_true', help='Expose actual generated records in the local example library')
    parser.add_argument('--max-tokens', type=int, default=96, choices=(64, 96, 128))
    args = parser.parse_args()
    runtime = LocalRuntime()
    runtime.load_async()
    runtime.load_thread.join()
    if runtime.state != 'ready':
        raise SystemExit(runtime.status()['message'])
    cancel = threading.Event()
    runs = []
    try:
        for prompt in PROMPTS:
            for strength in (.25, .5, 1):
                record = {'schema_version': 1, 'id': uuid.uuid4().hex, 'sequence': 0,
                    'created_at': datetime.now(timezone.utc).isoformat(), 'status': 'complete',
                    'request': {'schema_version': 1, 'recipe_id': RECIPE_ID, 'prompt': prompt,
                                'strength': strength, 'max_tokens': args.max_tokens},
                    'runtime': runtime.status(), 'outputs': {'original': '', 'remix': ''},
                    'metrics': {}, 'error': None, 'queue_position': None}
                for side, dose in (('original', 0), ('remix', strength)):
                    print(f'{side}: {strength}× / {prompt}', flush=True)
                    def on_text(text):
                        record['outputs'][side] += text
                    result = runtime.generate(prompt, dose, args.max_tokens, cancel, on_text)
                    record['metrics'][side] = asdict(result)
                runs.append(record)
                STATE_DIR.mkdir(exist_ok=True)
                (STATE_DIR / 'pilot.json').write_text(json.dumps({'recorded': True, 'comparisons': runs,
                    'review': 'Human review of coherence and useful dose range is still required.'}, indent=2) + '\n')
    except KeyboardInterrupt:
        cancel.set()
        raise SystemExit('Pilot interrupted. Completed pairs remain in .neuron-dj/pilot.json.')
    if args.save_examples:
        (STATE_DIR / 'examples.json').write_text(json.dumps({'recorded': True,
            'comparisons': [run for run in runs if run['request']['strength'] == .5]}, indent=2) + '\n')
    print('Saved .neuron-dj/pilot.json. Review tone, coherence, and timing before calling a dose validated.')


if __name__ == '__main__':
    main()
