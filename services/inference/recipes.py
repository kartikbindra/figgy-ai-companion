"""Allowlisted activation presets; coordinates are zero-based, signs are fixed."""
import copy
import hashlib
import json
from pathlib import Path

LEGACY_RECIPE = 'qwen-persona-pair-v1'
SOURCE = 'https://www.hedwigai.com/blog/qwen-personality-neurons'
_RECORDS = json.loads(Path(__file__).with_name('recipes.json').read_text())
_RECIPES = {r['id']: r for r in _RECORDS}
CATALOG_HASH = hashlib.sha256(json.dumps(_RECORDS, sort_keys=True).encode()).hexdigest()


def recipe(identifier=LEGACY_RECIPE):
    if not isinstance(identifier, str) or identifier not in _RECIPES:
        raise ValueError('Choose a supported activation personality.')
    result = copy.deepcopy(_RECIPES[identifier])
    result.setdefault('source', SOURCE)
    result.setdefault('note', '')
    result['evidence'] = 'Published coordinates; local personality quality is experimental.'
    return result


def catalog():
    return [recipe(identifier) for identifier in _RECIPES]


def components(identifier=LEGACY_RECIPE):
    return tuple(tuple(c) for c in recipe(identifier)['components'])


def all_components():
    # Signs do not affect calibration. Shared coordinates need only one coefficient.
    return tuple(sorted({(layer, neuron, 1) for r in _RECORDS for layer, neuron, sign in r['components']}))
