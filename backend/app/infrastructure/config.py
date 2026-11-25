"""Application settings loaded from environment variables."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration for archi-vite-v2 backend."""

    app_name: str = "archi-vite-v2"
    database_url: str = (
        "postgresql+psycopg://archivite:archivite_dev_secret@localhost:5436/archivite_v2"
    )
    redis_url: str = "redis://localhost:6379/0"
    storage_base_path: str = "./media"
    jwt_secret_key: str = "dev-insecure-change-me-in-production-min-32-bytes"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    """Return cached settings instance."""
    return Settings()
