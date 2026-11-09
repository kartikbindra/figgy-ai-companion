import pytest
from app.llm.mock import MockLLMProvider
from app.llm.ollama import OllamaProvider


@pytest.mark.asyncio
async def test_mock_provider_generate_and_stream():
    mock = MockLLMProvider()

    # Generate test
    reply = await mock.generate(
        prompt="Tell me something",
        system_prompt="[ACTIVE PERSONALITY: DARK COMEDIAN]"
    )
    assert len(reply) > 0
    assert "reality check" in reply.lower() or "medal" in reply.lower()

    # Stream test
    chunks = []
    async for chunk in mock.stream(
        prompt="Stream this",
        system_prompt="[ACTIVE PERSONALITY: DARK COMEDIAN]"
    ):
        chunks.append(chunk)

    combined = "".join(chunks)
    assert combined == reply

    # Health check
    health = await mock.health_check()
    assert health["status"] == "ok"


@pytest.mark.asyncio
async def test_ollama_provider_health_check_handles_offline():
    # Points to dummy port to verify graceful failure handling
    ollama = OllamaProvider(base_url="http://127.0.0.1:59999")
    health = await ollama.health_check()
    assert health["status"] == "disconnected"
    assert "error" in health
