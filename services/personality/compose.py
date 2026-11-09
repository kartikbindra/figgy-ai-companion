"""Conversation-local, validated personality settings and compact prompt rendering.

Profiles and mood rules adapted from Figgy, source revision 376ccad.
"""
from dataclasses import asdict, dataclass
import hashlib
import json
import math
from .profiles import PROFILES
from .mood import MoodAdapter


def number(value, name, low=0, high=1):
    if type(value) not in (int, float) or not math.isfinite(value) or not low <= value <= high:
        raise ValueError(f'{name} must be a finite number from {low} to {high}.')
    return float(value)


@dataclass(frozen=True)
class Personality:
    persona: str = 'dark_comedian'
    fusion: tuple[tuple[str, float], ...] = ()
    intensity: float = .85
    mood: bool = True
    memory: bool = True
    strength: float = 0
    max_tokens: int = 128

    @classmethod
    def parse(cls, value):
        if not isinstance(value, dict) or set(value) - set(cls.__dataclass_fields__):
            raise ValueError('Unsupported personality settings.')
        persona = value.get('persona', 'dark_comedian')
        if not isinstance(persona, str) or persona not in PROFILES:
            raise ValueError('Choose an available persona.')
        weights = value.get('fusion', {})
        if not isinstance(weights, dict) or any(k not in PROFILES for k in weights):
            raise ValueError('Fusion must map available personas to weights.')
        weights = {k: number(v, 'Fusion weight', high=1e9) for k, v in weights.items()}
        total = sum(weights.values())
        if weights and total <= 0:
            raise ValueError('Fusion needs at least one positive weight.')
        tokens = value.get('max_tokens', 128)
        if type(tokens) is not int or not 16 <= tokens <= 256:
            raise ValueError('Output limit must be an integer between 16 and 256.')
        for key in ('mood', 'memory'):
            if type(value.get(key, True)) is not bool:
                raise ValueError(f'{key} must be true or false.')
        return cls(persona, tuple(sorted((k, v / total) for k, v in weights.items() if v)),
                   number(value.get('intensity', .85), 'Intensity'), value.get('mood', True),
                   value.get('memory', True), number(value.get('strength', 0), 'Strength'), tokens)

    def document(self):
        return {**asdict(self), 'fusion': dict(self.fusion)}

    def render(self, message):
        selected = self.fusion or ((self.persona, 1.),)
        # A compact version fits the initial 768-token runtime, including fusion.
        lines = ['You are Figgy, a witty, observant companion. Reply conversationally in 2–4 sentences.',
                 f'Personality intensity: {self.intensity:.2f}.']
        for key, weight in selected:
            profile = PROFILES[key]
            lines.append(f'{profile.name} ({weight:.0%}): {profile.description}')
        mood = MoodAdapter.infer_contextual_mood(message) if self.mood else 'neutral'
        addition, _ = MoodAdapter.adapt_prompt_for_mood('', mood, 0)
        lines.append(addition)
        return '\n'.join(lines).strip(), mood


def catalog():
    return [{'id': p.id, 'name': p.name, 'description': p.description} for p in PROFILES.values()]


PROFILE_VERSION = 'figgy-compact-v1'
PROFILE_HASH = hashlib.sha256(json.dumps(catalog(), sort_keys=True).encode()).hexdigest()
