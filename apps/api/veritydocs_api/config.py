from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_env: str = "development"
    database_url: str = "sqlite:///./veritydocs.db"
    storage_backend: str = "local"
    storage_root: str = "./storage"
    s3_endpoint_url: str | None = None
    s3_bucket: str | None = None
    s3_access_key_id: str | None = None
    s3_secret_access_key: str | None = None
    s3_region: str = "us-east-1"
    s3_addressing_style: str = "path"
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
