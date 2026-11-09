"""Record real companion and matched method outputs, without opening a socket.

Stop the web service first: this command owns its own full model instance.
"""
import argparse
import json
from pathlib import Path
import sys
import time
import uuid

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from services.conversations.service import CompanionService
from services.inference.jobs import JobManager, TERMINAL
from services.inference.runtime import LocalRuntime, STATE_DIR
from services.storage.store import Store


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cpu', action='store_true')
    parser.add_argument('--prompt', default='Describe a quiet morning in two sentences.')
    parser.add_argument('--max-tokens', type=int, default=16)
    parser.add_argument('--strength', type=float, default=.25)
    parser.add_argument('--conditions', nargs='+', default=['baseline', 'prompt'],
                        choices=['baseline', 'prompt', 'activation', 'combined'])
    args = parser.parse_args()
    runtime = LocalRuntime()
    runtime.load_async(device='cpu' if args.cpu else None)
    runtime.load_thread.join()
    if runtime.status()['state'] != 'ready':
        raise SystemExit(runtime.status()['message'])
    # Pilot data is separate from the user's companion database.
    store = Store(STATE_DIR / 'unified-pilot.sqlite3')
    manager = JobManager(runtime, on_finish=store.finish, on_progress=store.checkpoint, deadline=3600)
    service = CompanionService(runtime, manager, store)
    records = {'recorded': True, 'runtime': runtime.status(), 'jobs': []}
    output = STATE_DIR / 'unified-pilot.json'
    def save():
        temporary = output.with_suffix('.tmp')
        temporary.write_text(json.dumps(records, indent=2, ensure_ascii=False) + '\n')
        temporary.replace(output)
    def wait(snapshot):
        while True:
            snapshot = manager.get(snapshot['id'])
            if snapshot['status'] in TERMINAL:
                records['jobs'].append(snapshot)
                save()
                if snapshot['status'] != 'complete':
                    raise RuntimeError(snapshot['error'] or snapshot['status'])
                return
            time.sleep(.25)
    try:
        conversation = store.create('Real-model integration pilot')
        settings = {**conversation['settings'], 'max_tokens': args.max_tokens, 'memory': False}
        store.settings(conversation['id'], settings)
        wait(service.chat(conversation['id'], {'message': args.prompt}, uuid.uuid4().hex))
        wait(service.experiment({'prompt': args.prompt, 'conditions': args.conditions,
                                 'settings': {**settings, 'strength': args.strength}}, uuid.uuid4().hex))
        runtime._verify_recovery()
        runtime._state('ready', 'Unified pilot complete; baseline recovery passed.')
        records['runtime_after'] = runtime.status()
        save()
        print(f'Recorded real outputs and recovery checks in {output}')
    finally:
        manager.close()
        manager.worker.join()
        manager.monitor.join()


if __name__ == '__main__':
    main()
