from dataclasses import dataclass, asdict
import hashlib
import json
import math
from .runtime import MODEL_ID, MODEL_REVISION, RECIPE_ID


@dataclass(frozen=True)
class ComparisonRequest:
    prompt: str
    strength: float = 0.5
    max_tokens: int = 128
    recipe_id: str = RECIPE_ID
    schema_version: int = 1

    @classmethod
    def parse(cls, value):
        if not isinstance(value, dict) or set(value) - {'prompt', 'strength', 'max_tokens', 'recipe_id', 'schema_version'}:
            raise ValueError('Unsupported comparison fields.')
        prompt = value.get('prompt')
        if not isinstance(prompt, str) or not prompt.strip() or len(prompt) > 4000:
            raise ValueError('Write a prompt between 1 and 4,000 characters.')
        strength = value.get('strength', 0.5)
        if type(strength) not in (int, float) or not math.isfinite(strength) or not 0 <= strength <= 1:
            raise ValueError('Strength must be a finite number from 0 to 1.')
        tokens = value.get('max_tokens', 128)
        if type(tokens) is not int or not 16 <= tokens <= 256:
            raise ValueError('Output limit must be an integer between 16 and 256.')
        if value.get('recipe_id', RECIPE_ID) != RECIPE_ID or value.get('schema_version', 1) != 1:
            raise ValueError('This recipe or schema is not supported by the local runtime.')
        return cls(prompt.strip(), float(strength), tokens)

    def fingerprint(self):
        return hashlib.sha256(json.dumps(asdict(self), sort_keys=True).encode()).hexdigest()


def recipe_metadata():
    return {'schema_version': 1, 'id': RECIPE_ID, 'name': 'The published pair',
            'model_id': MODEL_ID, 'model_revision': MODEL_REVISION,
            'source': 'https://github.com/shmuelamar/evil-qwen',
            'components': [{'layer': 14, 'neuron': 8949, 'dose': 1},
                           {'layer': 13, 'neuron': 7956, 'dose': -1}],
            'evidence': 'Published recipe; local dose/coherence pilot pending'}
