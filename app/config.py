import os
from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    LLM_BASE_URL: str = "https://openrouter.ai/api/v1"
    # Read from OPENROUTER_API_KEY; LLM_API_KEY still accepted for older .env files.
    LLM_API_KEY: str = Field("", validation_alias=AliasChoices("OPENROUTER_API_KEY", "LLM_API_KEY"))
    LLM_MODEL_NAME: str = "qwen/qwen3.5-9b"
    LLM_TEMPERATURE: float = 0.2
    OUTPUT_DIR: str = "data/outputs"
    TEMPLATE_DIR: str = "app/templates"
    REGULATION_CORPUS_DIR: str = "ocr_docs/typhoon_ocr"
    TOR_RULES_PATH: str = "app/tor/rules/tor_rules.yaml"
    TOR_MAX_REVISIONS: int = 2
    TOR_AUDIT_DIR: str = "data/audit"
    TOR_LLM_CONCURRENCY: int = 4
    # Semantic-rule judge: "llm" (generative judge) or "jev" (TypeSafe Jev decision model)
    TOR_JUDGE_BACKEND: str = "jev"
    JEV_MODEL_NAME: str = "typesafe/jev-1.13"
    JEV_DECISIONS_URL: str = "https://openrouter.ai/api/alpha/decisions"
    JEV_MAX_QUESTIONS_PER_REQUEST: int = 20

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

settings = Settings()
