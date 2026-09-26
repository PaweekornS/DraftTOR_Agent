import os
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    LLM_BASE_URL: str = "https://openrouter.ai/api/v1"
    LLM_API_KEY: str = ""
    LLM_MODEL_NAME: str = "qwen/qwen3.5-9b"
    LLM_TEMPERATURE: float = 0.2
    OUTPUT_DIR: str = "data/outputs"
    TEMPLATE_DIR: str = "app/templates"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

settings = Settings()
