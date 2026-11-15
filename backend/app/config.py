"""Application configuration with Vercel /tmp fallback support."""

import os
from functools import lru_cache
from pathlib import Path
from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict


def _is_vercel() -> bool:
    return os.environ.get("VERCEL", "").strip() == "1"


def _default_data_root() -> Path:
    if _is_vercel():
        return Path("/tmp/contractmind")
    return Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    """Runtime settings for ContractMind v2.0."""

    APP_NAME: str = "ContractMind v2.0"
    APP_VERSION: str = "2.0.0"
    DEBUG: bool = False

    VERCEL: str = os.environ.get("VERCEL", "0")
    DATABASE_URL: str = ""
    CHROMA_PERSIST_DIR: str = ""
    UPLOAD_DIR: str = ""

    DEFAULT_LLM_PROVIDER: str = "simulator"
    GEMINI_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-3.5-flash-lite"
    OPENAI_API_KEY: str = ""
    OPENAI_MODEL: str = "gpt-4o"
    ANTHROPIC_API_KEY: str = ""
    ANTHROPIC_MODEL: str = "claude-3-5-sonnet"
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "qwen3.5:4b"

    SECRET_KEY: str = "contractmind-dev-secret-change-in-prod"
    CORS_ORIGINS: str = "*"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    def model_post_init(self, __context) -> None:
        root = _default_data_root()
        if not self.DATABASE_URL:
            db_path = root / "contractmind.db"
            self.DATABASE_URL = f"sqlite+aiosqlite:///{db_path.as_posix()}"
        if not self.CHROMA_PERSIST_DIR:
            self.CHROMA_PERSIST_DIR = (root / "chroma_db").as_posix()
        if not self.UPLOAD_DIR:
            self.UPLOAD_DIR = (root / "uploads").as_posix()

        Path(self.CHROMA_PERSIST_DIR).mkdir(parents=True, exist_ok=True)
        Path(self.UPLOAD_DIR).mkdir(parents=True, exist_ok=True)

    @property
    def cors_origin_list(self) -> List[str]:
        if self.CORS_ORIGINS.strip() == "*":
            return ["*"]
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
