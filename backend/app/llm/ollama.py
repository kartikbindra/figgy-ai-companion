import json
from typing import AsyncIterator, Dict, Any, Optional
import httpx
from app.llm.base import LLMProvider
from app.core.config import settings
from app.core.logging import logger


class OllamaProvider(LLMProvider):
    """Ollama API integration supporting single generation, streaming, and health checks."""

    def __init__(self, base_url: Optional[str] = None, model: Optional[str] = None):
        self.base_url = (base_url or settings.OLLAMA_HOST).rstrip("/")
        self.model = model or settings.LLM_MODEL
        self.timeout = settings.LLM_TIMEOUT

    async def generate(
        self,
        prompt: str,
        system_prompt: str = "",
        temperature: Optional[float] = None,
        **kwargs: Any
    ) -> str:
        temp = temperature if temperature is not None else settings.LLM_TEMPERATURE
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "think": False,
            "keep_alive": "24h",
            "options": {
                "temperature": temp,
                "num_predict": 120,
                "num_ctx": 2048
            }
        }

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                response = await client.post(f"{self.base_url}/api/chat", json=payload)
                response.raise_for_status()
                data = response.json()
                return data.get("message", {}).get("content", "")
            except httpx.ConnectError:
                logger.error(f"Cannot connect to Ollama server at {self.base_url}. Ensure Ollama is running.")
                raise ConnectionError(f"Ollama server unavailable at {self.base_url}")
            except httpx.HTTPStatusError as e:
                logger.error(f"Ollama API returned error: {e.response.status_code} - {e.response.text}")
                raise

    async def stream(
        self,
        prompt: str,
        system_prompt: str = "",
        temperature: Optional[float] = None,
        **kwargs: Any
    ) -> AsyncIterator[str]:
        temp = temperature if temperature is not None else settings.LLM_TEMPERATURE
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": self.model,
            "messages": messages,
            "stream": True,
            "think": False,
            "keep_alive": "24h",
            "options": {
                "temperature": temp,
                "num_predict": 120,
                "num_ctx": 2048
            }
        }

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                async with client.stream("POST", f"{self.base_url}/api/chat", json=payload) as response:
                    response.raise_for_status()
                    async for line in response.aiter_lines():
                        if not line:
                            continue
                        try:
                            chunk = json.loads(line)
                            token = chunk.get("message", {}).get("content", "")
                            if token:
                                yield token
                            if chunk.get("done", False):
                                break
                        except json.JSONDecodeError:
                            continue
            except httpx.ConnectError:
                logger.error(f"Cannot connect to Ollama streaming endpoint at {self.base_url}")
                raise ConnectionError(f"Ollama server unavailable at {self.base_url}")

    async def health_check(self) -> Dict[str, Any]:
        async with httpx.AsyncClient(timeout=5.0) as client:
            try:
                resp = await client.get(f"{self.base_url}/api/tags")
                if resp.status_code == 200:
                    data = resp.json()
                    models = [m.get("name") for m in data.get("models", [])]
                    model_found = any(self.model in m for m in models)
                    return {
                        "status": "connected",
                        "provider": "ollama",
                        "host": self.base_url,
                        "configured_model": self.model,
                        "model_available": model_found,
                        "installed_models": models
                    }
                return {"status": "unhealthy", "code": resp.status_code}
            except Exception as e:
                return {
                    "status": "disconnected",
                    "provider": "ollama",
                    "host": self.base_url,
                    "error": str(e)
                }
