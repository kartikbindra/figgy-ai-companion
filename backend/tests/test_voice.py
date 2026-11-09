import pytest
from httpx import AsyncClient
from app.voice.tts import TTSEngine, VOICE_OPTIONS


def test_voice_options_list():
    options = TTSEngine.get_voice_options()
    assert len(options) >= 5
    ids = [o["id"] for o in options]
    assert "en-US-GuyNeural" in ids
    assert "en-GB-RyanNeural" in ids
    assert "en-US-ChristopherNeural" in ids


@pytest.mark.asyncio
async def test_api_voice_options(async_client: AsyncClient):
    resp = await async_client.get("/v1/voice/options")
    assert resp.status_code == 200
    data = resp.json()
    assert "voices" in data
    assert len(data["voices"]) >= 5


@pytest.mark.asyncio
async def test_api_voice_synthesis(async_client: AsyncClient):
    payload = {
        "text": "Hey there, I am Figgy.",
        "voice": "en-US-GuyNeural"
    }
    resp = await async_client.post("/v1/voice/synthesize", json=payload)
    assert resp.status_code == 200
    assert "audio/mpeg" in resp.headers["content-type"]
    assert len(resp.content) > 100
