from typing import Tuple

# Keywords indicating specific emotional states
MOOD_INDICATORS = {
    "distressed": [
        "crying", "breakup", "died", "grief", "hopeless", "panic", "anxiety",
        "scared", "terrified", "hurts so much", "depressed", "can't take this"
    ],
    "frustrated": [
        "hate this", "so annoying", "pissed", "furious", "angry", "broken again",
        "stupid bug", "sick of this", "waste of time"
    ],
    "tired": [
        "exhausted", "sleepy", "tired", "burned out", "drained", "can't sleep",
        "2 am", "3 am", "4 am", "no energy"
    ],
    "bored": [
        "bored", "nothing to do", "entertain me", "dull", "uninspired"
    ],
    "excited": [
        "let's go", "amazing", "hyped", "thrilled", "we did it", "holy shit it worked",
        "huge win", "celebrating"
    ]
}


class MoodAdapter:
    @staticmethod
    def infer_contextual_mood(user_message: str) -> str:
        """Heuristic contextual mood inference from the user message."""
        lower = user_message.lower()
        for mood, keywords in MOOD_INDICATORS.items():
            if any(kw in lower for kw in keywords):
                return mood
        return "neutral"

    @staticmethod
    def adapt_prompt_for_mood(base_prompt: str, mood: str, roast_level: float) -> Tuple[str, str]:
        """
        Adjust instructions based on inferred mood to ensure Figgy responds perceptively.
        Returns (modified_prompt_addition, mood_label).
        """
        if mood == "distressed":
            note = (
                "\n[CONTEXTUAL MOOD OVERRIDE: USER IS DISTRESSED]\n"
                "- The user appears genuinely sad, hurting, or distressed.\n"
                "- IMMEDIATELY SUSPEND heavy roasts, mockery, or harsh comebacks.\n"
                "- Be perceptive, present, and authentically supportive while still retaining your unique wit and warmth."
            )
            return note, mood

        elif mood == "frustrated":
            note = (
                "\n[CONTEXTUAL MOOD NOTE: USER IS FRUSTRATED]\n"
                "- The user is venting or angry. Validate their frustration with shared cynicism rather than mocking their struggle."
            )
            return note, mood

        elif mood == "tired":
            note = (
                "\n[CONTEXTUAL MOOD NOTE: USER IS EXHAUSTED]\n"
                "- Keep the response brief, gentle, and wry. Do not overwhelm them with lengthy monologues."
            )
            return note, mood

        elif mood == "bored":
            note = (
                "\n[CONTEXTUAL MOOD NOTE: USER IS BORED]\n"
                "- Be especially sharp, provocative, and entertaining to shake them out of their stupor."
            )
            return note, mood

        elif mood == "excited":
            note = (
                "\n[CONTEXTUAL MOOD NOTE: USER IS HYPED]\n"
                "- Match their energy! Celebrate with witty hype."
            )
            return note, mood

        return "", mood
