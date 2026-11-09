import io
import os
import tempfile
from typing import Optional
from app.core.logging import logger

_whisper_model = None


def get_whisper_model():
    global _whisper_model
    if _whisper_model is None:
        from faster_whisper import WhisperModel
        logger.info("Initializing Faster-Whisper (tiny.en on CPU with int8)...")
        _whisper_model = WhisperModel("tiny.en", device="cpu", compute_type="int8")
        logger.info("Faster-Whisper initialized.")
    return _whisper_model


class STTEngine:
    @staticmethod
    def transcribe(audio_bytes: bytes) -> str:
        """Transcribe audio bytes (WAV, WebM, MP3, OGG) to text using faster-whisper."""
        model = get_whisper_model()

        # Write to temporary file for libsndfile / ctranslate2 decoding
        with tempfile.NamedTemporaryFile(suffix=".webm", delete=False) as tmp:
            tmp.write(audio_bytes)
            tmp_path = tmp.name

        try:
            segments, info = model.transcribe(tmp_path, beam_size=1)
            transcribed_text = " ".join([seg.text.strip() for seg in segments]).strip()
            logger.info(f"Transcribed audio ({info.duration:.2f}s): '{transcribed_text}'")
            return transcribed_text
        except Exception as e:
            logger.error(f"Error in STT transcription: {e}")
            raise
        finally:
            if os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                except Exception:
                    pass
