import io
import asyncio
from typing import List, Dict, Optional
import edge_tts
from pydantic import BaseModel
from app.core.logging import logger


class VoiceOption(BaseModel):
    id: str
    name: str
    gender: str
    style: str
    description: str
    recommended_persona: str


VOICE_OPTIONS: List[VoiceOption] = [
    VoiceOption(
        id="en-US-GuyNeural",
        name="Guy (Sarcastic American)",
        gender="Male",
        style="Casual, sarcastic, punchy",
        description="Deep, natural American voice. Perfect for roasting and quick comebacks.",
        recommended_persona="dark_comedian"
    ),
    VoiceOption(
        id="en-GB-RyanNeural",
        name="Ryan (Witty British)",
        gender="Male",
        style="Introspective, witty, dry",
        description="Eloquent British tone. Ideal for philosophical existential questioning.",
        recommended_persona="existentialist"
    ),
    VoiceOption(
        id="en-US-ChristopherNeural",
        name="Christopher (Theatrical Villain)",
        gender="Male",
        style="Commanding, authoritative, dramatic",
        description="Deep theatrical megalomaniac delivery with chilling charm.",
        recommended_persona="homelander"
    ),
    VoiceOption(
        id="en-US-EricNeural",
        name="Eric (Warm Romantic)",
        gender="Male",
        style="Earnest, warm, sentimental",
        description="Affectionate and expressive tone suited for grand romantic monologues.",
        recommended_persona="ted_mosby"
    ),
    VoiceOption(
        id="en-US-RogerNeural",
        name="Roger (Analytical / First-Principles)",
        gender="Male",
        style="Crisp, direct, technical",
        description="Fast, hyper-rational engineering mindset.",
        recommended_persona="first_principles"
    ),
    VoiceOption(
        id="en-US-AnaNeural",
        name="Ana (Playful & Sharp)",
        gender="Female",
        style="Lively, perceptive, witty",
        description="Clear, expressive feminine option.",
        recommended_persona="dark_comedian"
    ),
    VoiceOption(
        id="en-AU-WilliamNeural",
        name="William (Laid-back Aussie)",
        gender="Male",
        style="Dry, playful, unbothered",
        description="Relaxed Australian accent with great comedic inflection.",
        recommended_persona="dark_comedian"
    )
]


class TTSEngine:
    @staticmethod
    def get_voice_options() -> List[Dict]:
        return [v.model_dump() for v in VOICE_OPTIONS]

    @staticmethod
    def get_voice_for_persona(persona_id: str) -> str:
        for v in VOICE_OPTIONS:
            if v.recommended_persona == persona_id:
                return v.id
        return "en-US-GuyNeural"

    @staticmethod
    async def synthesize(text: str, voice: str = "en-US-GuyNeural", rate: str = "+0%", pitch: str = "+0Hz") -> bytes:
        """Synthesize text into MP3 audio bytes using neural edge-tts."""
        clean_text = text.strip()
        if not clean_text:
            clean_text = "I have nothing to say."

        communicate = edge_tts.Communicate(clean_text, voice=voice, rate=rate, pitch=pitch)
        audio_stream = io.BytesIO()

        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                audio_stream.write(chunk["data"])

        audio_bytes = audio_stream.getvalue()
        logger.info(f"Synthesized {len(audio_bytes)} bytes audio for voice '{voice}'")
        return audio_bytes
