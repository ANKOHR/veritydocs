from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_env: str = "development"
    database_url: str = "sqlite:///./veritydocs.db"
    storage_root: str = "./storage"
    ocr_engine: str = "tesseract"
    extraction_provider: str = "demo"
    openai_api_key: str | None = None
    openai_model: str = "gpt-4.1-mini"
    redis_url: str | None = None
    pipeline_version: str = "veritydocs-pipeline-0.1"
    model_config = SettingsConfigDict(env_file=(".env", ".env.local"), extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()
