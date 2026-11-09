from abc import ABC, abstractmethod
from typing import AsyncIterator, Dict, Any, Optional


class LLMProvider(ABC):
    """Abstract interface for LLM providers (Ollama, llama.cpp, mock, etc.)."""

    @abstractmethod
    async def generate(
        self,
        prompt: str,
        system_prompt: str = "",
        temperature: Optional[float] = None,
        **kwargs: Any
    ) -> str:
        """Generate a single complete response string."""
        pass

    @abstractmethod
    async def stream(
        self,
        prompt: str,
        system_prompt: str = "",
        temperature: Optional[float] = None,
        **kwargs: Any
    ) -> AsyncIterator[str]:
        """Stream response tokens as an asynchronous generator."""
        pass

    @abstractmethod
    async def health_check(self) -> Dict[str, Any]:
        """Check if provider and model are available."""
        pass
