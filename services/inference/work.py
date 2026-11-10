"""Immutable v2 work contracts; v1 comparison contracts remain supported."""
from dataclasses import asdict, dataclass
import hashlib
import json
from .recipes import LEGACY_RECIPE


@dataclass(frozen=True)
class Message:
    role: str
    content: str


@dataclass(frozen=True)
class Leg:
    name: str
    messages: tuple[Message, ...]
    strength: float
    recipe_id: str = LEGACY_RECIPE


@dataclass(frozen=True)
class WorkRequest:
    kind: str
    prompt: str
    legs: tuple[Leg, ...]
    max_tokens: int
    provenance: str
    conversation_id: str | None = None
    schema_version: int = 2

    def fingerprint(self):
        return hashlib.sha256(json.dumps(asdict(self), sort_keys=True).encode()).hexdigest()


def prompt_text(value):
    if not isinstance(value, str) or not value.strip() or len(value) > 4000:
        raise ValueError('Write a message between 1 and 4,000 characters.')
    return value.strip()
