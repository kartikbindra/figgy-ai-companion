from typing import Dict
from app.personality.profiles import PROFILES


def compose_fusion_prompt(weights: Dict[str, float], intensity: float = 0.85) -> str:
    """
    Synthesize instructions for blending multiple personalities based on normalized weights.
    e.g., {"dark_comedian": 0.7, "existentialist": 0.3}
    """
    if not weights:
        return PROFILES["dark_comedian"].system_prompt

    total = sum(weights.values())
    if total <= 0:
        normalized = {"dark_comedian": 1.0}
    else:
        normalized = {k: v / total for k, v in weights.items() if k in PROFILES and v > 0}

    if len(normalized) == 1:
        single_key = next(iter(normalized))
        return PROFILES[single_key].system_prompt

    lines = [
        "[ACTIVE PERSONALITY: DYNAMIC FUSION]",
        f"You are blending {len(normalized)} personality modes simultaneously with an overall intensity of {intensity:.2f}:"
    ]

    for key, weight in normalized.items():
        profile = PROFILES[key]
        pct = int(weight * 100)
        lines.append(f"\n- Mode: {profile.name} (Weight: {pct}%)")
        lines.append(f"  Traits: {', '.join(profile.traits)}")
        lines.append(f"  Core Focus: {profile.description}")

    lines.append(
        "\nHOW TO BLEND:"
        "\n1. Seamlessly interweave these distinct voices into one cohesive, multi-faceted response."
        "\n2. Let the highest-weighted personality dictate your immediate attitude and tone, while incorporating elements, metaphors, and insights from the secondary personalities."
        "\n3. Never announce or say 'As 60% comedian and 40% existentialist'—simply BE this unique composite consciousness."
    )
    return "\n".join(lines)
