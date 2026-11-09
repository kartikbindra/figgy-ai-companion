import argparse
import os
import webbrowser
import uvicorn
from services.api.app import create_app
from services.inference.runtime import LocalRuntime


def main():
    parser = argparse.ArgumentParser(description='Local companion and experiment studio')
    parser.add_argument('--port', type=int, default=8791)
    parser.add_argument('--load-model', action='store_true')
    parser.add_argument('--open', action='store_true')
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        parser.error('Port must be between 1 and 65535.')
    provider = os.environ.get('NEURON_DJ_PROVIDER', 'transformers')
    if provider == 'ollama':
        from services.providers.ollama import OllamaRuntime
        runtime = OllamaRuntime()
    elif provider == 'transformers':
        runtime = LocalRuntime()
    else:
        parser.error('NEURON_DJ_PROVIDER must be transformers or ollama.')
    if args.load_model:
        runtime.load_async()
    url = f'http://127.0.0.1:{args.port}'
    print(f'Companion + Neuron DJ → {url}', flush=True)
    if args.open:
        import threading
        threading.Timer(1, lambda: webbrowser.open(url)).start()
    uvicorn.run(create_app(runtime=runtime, port=args.port), host='127.0.0.1', port=args.port,
                workers=1, access_log=False, log_level='warning')


if __name__ == '__main__':
    main()
