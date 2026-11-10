"""Terminal client for the unified companion API (no extra dependencies)."""
import argparse
import json
from urllib.request import Request, urlopen
import uuid


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--url', default='http://127.0.0.1:8791')
    parser.add_argument('--conversation', help='Resume a conversation ID')
    parser.add_argument('--persona', default='dark_comedian')
    parser.add_argument('--strength', type=float, default=0)
    parser.add_argument('--activation-recipe', help='Activation preset ID from /api/recipes; preserves the current selection when omitted')
    args = parser.parse_args()
    def api(path, body=None, method=None, key=None):
        data = json.dumps(body).encode() if body is not None else None
        headers = {'Content-Type': 'application/json'} if data else {}
        if key:
            headers['Idempotency-Key'] = key
        req = Request(args.url.rstrip('/') + path, data, headers, method=method)
        with urlopen(req, timeout=660) as response:
            return json.load(response)
    conversation = api(f'/api/v2/conversations/{args.conversation}') if args.conversation else api('/api/v2/conversations', {'title': 'Terminal conversation'})
    identifier = conversation['id']
    settings = {**conversation['settings'], 'persona': args.persona, 'fusion': {}, 'strength': args.strength}
    if args.activation_recipe:
        settings['activation_recipe'] = args.activation_recipe
    api(f'/api/v2/conversations/{identifier}/settings', settings, 'PUT')
    print(f'Conversation {identifier}. /quit exits; Ctrl+C stops the current turn.')
    while True:
        try:
            message = input('\nYou: ').strip()
        except (EOFError, KeyboardInterrupt):
            return
        if message == '/quit':
            return
        if not message:
            continue
        job = None
        try:
            job = api(f'/api/v2/conversations/{identifier}/turns', {'message': message}, key=uuid.uuid4().hex)
            printed = ''
            print('Figgy: ', end='', flush=True)
            with urlopen(args.url.rstrip('/') + f"/api/v2/jobs/{job['id']}/events", timeout=660) as response:
                for line in response:
                    if line.startswith(b'data: '):
                        snapshot = json.loads(line[6:])['job']
                        output = snapshot['outputs']['reply']
                        print(output[len(printed):], end='', flush=True)
                        printed = output
                        if snapshot.get('error'):
                            print(f"\n{snapshot['error']}")
            print()
        except KeyboardInterrupt:
            if job:
                api(f"/api/v2/jobs/{job['id']}", method='DELETE')
            print('\nStop requested; cleanup may still be running.')
        except Exception as exc:
            print(f'Could not complete this turn: {exc}')


if __name__ == '__main__':
    main()
