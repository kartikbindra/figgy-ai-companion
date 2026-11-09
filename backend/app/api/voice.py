import base64
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Depends, Response
from fastapi.responses import StreamingResponse
import io
from pydantic import BaseModel, Field
from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession

from app.voice.tts import TTSEngine
from app.voice.stt import STTEngine
from app.llm.orchestrator import orchestrator
from app.database.connection import get_db
from app.personality.manager import personality_manager
from app.core.security import verify_api_key
from app.core.logging import logger

router = APIRouter(prefix="/voice", tags=["Voice"])


class SynthesizeRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=1000)
    voice: Optional[str] = Field(default=None, description="Voice ID or auto-selected by persona")
    rate: Optional[str] = Field(default="+0%")
    pitch: Optional[str] = Field(default="+0Hz")


@router.get("/options", dependencies=[Depends(verify_api_key)])
async def get_voice_options():
    """Retrieve available TTS voices with character descriptions and recommended personas."""
    return {
        "active_persona": personality_manager.active_persona,
        "recommended_voice": TTSEngine.get_voice_for_persona(personality_manager.active_persona),
        "voices": TTSEngine.get_voice_options()
    }


@router.post("/synthesize", dependencies=[Depends(verify_api_key)])
async def synthesize_speech(req: SynthesizeRequest):
    """Synthesize text into MP3 audio stream."""
    try:
        voice = req.voice or TTSEngine.get_voice_for_persona(personality_manager.active_persona)
        audio_bytes = await TTSEngine.synthesize(req.text, voice=voice, rate=req.rate or "+0%", pitch=req.pitch or "+0Hz")
        return Response(content=audio_bytes, media_type="audio/mpeg")
    except Exception as e:
        logger.error(f"Speech synthesis failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/transcribe", dependencies=[Depends(verify_api_key)])
async def transcribe_speech(audio: UploadFile = File(...)):
    """Transcribe uploaded audio file to text using Faster-Whisper."""
    try:
        audio_bytes = await audio.read()
        if not audio_bytes:
            raise HTTPException(status_code=400, detail="Empty audio file provided")
        transcript = STTEngine.transcribe(audio_bytes)
        return {"transcript": transcript}
    except Exception as e:
        logger.error(f"Transcription failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/chat", dependencies=[Depends(verify_api_key)])
async def voice_chat(
    audio: UploadFile = File(...),
    conversation_id: str = Form("voice-session"),
    voice: Optional[str] = Form(None),
    session: AsyncSession = Depends(get_db)
):
    """
    End-to-End Voice Turn:
    1. Transcribe audio microphone recording (STT)
    2. Route transcript into Figgy's personality & memory orchestrator
    3. Synthesize assistant response into voice audio (TTS)
    4. Return transcript, text reply, and base64 encoded audio
    """
    try:
        audio_bytes = await audio.read()
        if not audio_bytes:
            raise HTTPException(status_code=400, detail="Empty audio recording")

        # 1. Transcribe
        user_message = STTEngine.transcribe(audio_bytes)
        if not user_message:
            user_message = "[Unintelligible speech]"

        # 2. Chat completion
        reply, persona, mood = await orchestrator.chat(
            session=session,
            conversation_id=conversation_id,
            user_message=user_message,
            device_id="voice-client"
        )

        # 3. Synthesize speech
        selected_voice = voice or TTSEngine.get_voice_for_persona(persona)
        speech_bytes = await TTSEngine.synthesize(reply, voice=selected_voice)
        audio_b64 = base64.b64encode(speech_bytes).decode("ascii")

        return {
            "conversation_id": conversation_id,
            "user_transcript": user_message,
            "reply": reply,
            "persona": persona,
            "mood": mood,
            "voice": selected_voice,
            "audio_base64": audio_b64,
            "audio_format": "audio/mpeg"
        }
    except Exception as e:
        logger.error(f"Voice chat failure: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
