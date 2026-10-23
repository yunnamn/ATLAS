from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="ATLAS_", env_file=".env", extra="ignore")
    database_url: str = "sqlite:///./data/atlas.db"
    cors_origins: list[str] = ["http://127.0.0.1:5173", "http://localhost:5173"]

    llm_enabled: bool = False
    llm_base_url: str | None = None
    llm_model: str | None = None
    llm_api_key: SecretStr | None = None
    llm_json_mode: Literal["json_schema", "json_object"] = "json_schema"
    llm_timeout_seconds: float = Field(default=20, ge=1, le=30)
    llm_retries: int = Field(default=1, ge=0, le=1)
    llm_max_output_tokens: int = Field(default=1800, ge=256, le=3000)
    search_base_url: str | None = None
    search_api_key: SecretStr | None = None
    research_cache_seconds: int = Field(default=3600, ge=0, le=86400)
    research_min_interval: float = Field(default=1, ge=0.5, le=5)


settings = Settings()
if settings.database_url.startswith("sqlite:///./data/"):
    Path("data").mkdir(exist_ok=True)
