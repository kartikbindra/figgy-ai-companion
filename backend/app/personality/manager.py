from typing import Dict, Optional, Tuple
from app.personality.profiles import PROFILES, CORE_IDENTITY, PersonalityProfile
from app.personality.fusion import compose_fusion_prompt
from app.personality.mood import MoodAdapter
from app.core.config import settings


class PersonalityManager:
    def __init__(self):
        self.active_mode: str = "single"  # "single" or "fusion"
        self.active_persona: str = settings.DEFAULT_PERSONA
        self.intensity: float = settings.DEFAULT_INTENSITY
        self.fusion_weights: Dict[str, float] = {
            "dark_comedian": 0.5,
            "existentialist": 0.5
        }

    def set_single_persona(self, persona_id: str, intensity: Optional[float] = None) -> PersonalityProfile:
        if persona_id not in PROFILES:
            raise ValueError(f"Unknown persona: {persona_id}. Valid personas: {list(PROFILES.keys())}")
        self.active_mode = "single"
        self.active_persona = persona_id
        if intensity is not None:
            self.intensity = max(0.1, min(1.0, intensity))
        return PROFILES[persona_id]

    def set_fusion(self, weights: Dict[str, float], intensity: Optional[float] = None) -> Dict[str, float]:
        for k in weights.keys():
            if k not in PROFILES:
                raise ValueError(f"Unknown persona '{k}' in fusion weights. Valid personas: {list(PROFILES.keys())}")
        self.active_mode = "fusion"
        self.fusion_weights = weights
        if intensity is not None:
            self.intensity = max(0.1, min(1.0, intensity))
        return self.fusion_weights

    def get_status(self) -> Dict:
        return {
            "mode": self.active_mode,
            "active_persona": self.active_persona if self.active_mode == "single" else None,
            "fusion_weights": self.fusion_weights if self.active_mode == "fusion" else None,
            "intensity": self.intensity,
            "available_personas": [
                {
                    "id": p.id,
                    "name": p.name,
                    "title": p.title,
                    "description": p.description,
                    "traits": p.traits
                }
                for p in PROFILES.values()
            ]
        }

    def build_system_prompt(self, user_message: str = "") -> Tuple[str, str, str]:
        """
        Assemble the full system prompt including:
        1. Core Figgy identity
        2. Active personality or fusion instructions
        3. Intensity scaling
        4. Contextual mood adaptation
        Returns: (system_prompt, active_persona_label, inferred_mood)
        """
        mood = MoodAdapter.infer_contextual_mood(user_message) if user_message else "neutral"

        if self.active_mode == "fusion":
            persona_section = compose_fusion_prompt(self.fusion_weights, self.intensity)
            persona_label = "fusion:" + "+".join(self.fusion_weights.keys())
            roast_level = 0.5
        else:
            profile = PROFILES.get(self.active_persona, PROFILES["dark_comedian"])
            persona_section = (
                f"{profile.system_prompt}\n"
                f"[INTENSITY: {self.intensity:.2f}/1.0] Express these persona traits with "
                f"{'maximum unhinged conviction' if self.intensity > 0.8 else 'moderate subtlety'}."
            )
            persona_label = profile.id
            roast_level = profile.roast_level

        mood_addition, mood_label = MoodAdapter.adapt_prompt_for_mood(persona_section, mood, roast_level)

        full_prompt = (
            f"{CORE_IDENTITY}\n\n"
            f"{persona_section}"
            f"{mood_addition}"
        )

        return full_prompt, persona_label, mood_label


personality_manager = PersonalityManager()
