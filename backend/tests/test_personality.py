import pytest
from app.personality.profiles import PROFILES
from app.personality.manager import PersonalityManager
from app.personality.mood import MoodAdapter
from app.personality.fusion import compose_fusion_prompt


def test_all_five_profiles_exist():
    expected = ["dark_comedian", "existentialist", "first_principles", "ted_mosby", "homelander"]
    for p_id in expected:
        assert p_id in PROFILES
        profile = PROFILES[p_id]
        assert profile.name
        assert profile.system_prompt
        assert len(profile.traits) > 0


def test_personality_manager_switch():
    pm = PersonalityManager()
    assert pm.active_persona == "dark_comedian"

    pm.set_single_persona("homelander", intensity=0.95)
    assert pm.active_persona == "homelander"
    assert pm.intensity == 0.95

    prompt, label, mood = pm.build_system_prompt("Hello Figgy")
    assert label == "homelander"
    assert "THE UNHINGED VILLAIN" in prompt
    assert "INTENSITY: 0.95" in prompt


def test_fusion_prompt_generation():
    pm = PersonalityManager()
    weights = {"dark_comedian": 0.6, "existentialist": 0.4}
    pm.set_fusion(weights, intensity=0.8)

    prompt, label, mood = pm.build_system_prompt("What is life?")
    assert "fusion" in label
    assert "DYNAMIC FUSION" in prompt
    assert "The Dark Comedian (Weight: 60%)" in prompt
    assert "The Existentialist (Weight: 40%)" in prompt


def test_mood_detection_and_adaptation():
    # Test distressed mood override
    msg = "I'm crying and terrified, I can't take this anymore"
    mood = MoodAdapter.infer_contextual_mood(msg)
    assert mood == "distressed"

    note, mood_lbl = MoodAdapter.adapt_prompt_for_mood("base prompt", mood, 0.9)
    assert "USER IS DISTRESSED" in note
    assert "IMMEDIATELY SUSPEND heavy roasts" in note

    # Test excited mood
    msg2 = "Holy shit it worked, we did it!"
    mood2 = MoodAdapter.infer_contextual_mood(msg2)
    assert mood2 == "excited"
