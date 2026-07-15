from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "docintel"
    environment: str = "development"

    database_url: str = "postgresql+psycopg://docintel:docintel_dev@localhost:5432/docintel"
    redis_url: str = "redis://localhost:6379/0"

    storage_backend: str = "local"          # "local" | "s3"
    storage_local_path: str = "./storage"

    confidence_strategy: str = "min_gated"
    confidence_threshold: float = 0.70   # below this → review (Engine 4, Day 8)

    max_upload_bytes: int = 25 * 1024 * 1024  # 25 MB

    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "qwen2.5:7b-instruct"


@lru_cache
def get_settings() -> Settings:
    return Settings()