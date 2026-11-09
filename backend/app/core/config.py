from pydantic_settings import BaseSettings
from pydantic import ConfigDict
from typing import Optional


class Settings(BaseSettings):
    PROJECT_NAME: str = "Figgy AI Companion Backend"
    VERSION: str = "0.1.0"
    API_V1_STR: str = "/v1"
    
    # LLM Settings
    LLM_PROVIDER: str = "ollama"  # "ollama", "mock"
    OLLAMA_HOST: str = "http://localhost:11434"
    LLM_MODEL: str = "huihui_ai/qwen3-abliterated"
    LLM_TEMPERATURE: float = 0.8
    LLM_TIMEOUT: float = 120.0
    MAX_CONTEXT_TOKENS: int = 4096
    
    # Personality Defaults
    DEFAULT_PERSONA: str = "dark_comedian"
    DEFAULT_INTENSITY: float = 0.85
    
    # Memory Settings
    DATABASE_URL: str = "sqlite+aiosqlite:///./figgy.db"
    MAX_WORKING_MEMORY_TURNS: int = 10
    AUTO_EXTRACT_MEMORY: bool = True
    
    # Security
    API_KEY: Optional[str] = "figgy-secret-key"
    REQUIRE_API_KEY: bool = False  # Set to True for production/remote deployment
    
    # Hardware/Device Defaults
    DEFAULT_DEVICE_ID: str = "figgy-001"

    model_config = ConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )


settings = Settings()
