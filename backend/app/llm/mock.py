import asyncio
from typing import AsyncIterator, Dict, Any, Optional
from app.llm.base import LLMProvider


class MockLLMProvider(LLMProvider):
    """Deterministic mock provider for unit testing and offline development."""

    def __init__(self, canned_reply: Optional[str] = None):
        self.canned_reply = canned_reply

    async def generate(
        self,
        prompt: str,
        system_prompt: str = "",
        temperature: Optional[float] = None,
        **kwargs: Any
    ) -> str:
        if self.canned_reply:
            return self.canned_reply

        if "DARK COMEDIAN" in system_prompt:
            return "Oh fantastic, another life update. Did you want a medal or a reality check?"
        elif "EXISTENTIALIST" in system_prompt:
            return "We are mere shadows seeking warmth in an indifferent universe."
        elif "FIRST-PRINCIPLES" in system_prompt:
            return "Fundamentally, this is an optimization problem governed by thermodynamic constraints."
        elif "HOPELESS ROMANTIC" in system_prompt:
            return "Don't you see? Every coincidence is the universe whispering your destiny."
        elif "UNHINGED VILLAIN" in system_prompt:
            return "I could shatter your digital existence with a flick of my finger. Be grateful I'm listening."
        return "Figgy is observing you silently."

    async def stream(
        self,
        prompt: str,
        system_prompt: str = "",
        temperature: Optional[float] = None,
        **kwargs: Any
    ) -> AsyncIterator[str]:
        full_text = await self.generate(prompt, system_prompt, temperature, **kwargs)
        words = full_text.split(" ")
        for i, word in enumerate(words):
            yield word + (" " if i < len(words) - 1 else "")
            await asyncio.sleep(0.01)

    async def health_check(self) -> Dict[str, Any]:
        return {"status": "ok", "provider": "mock", "model": "mock-qwen3-4b-abliterated"}
