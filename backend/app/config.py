"""Application configuration with automatic Vercel /tmp path fallback."""

from __future__ import annotations

import os
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


BACKEND_ROOT = Path(__file__).resolve().parent.parent


def _is_vercel() -> bool:
    return os.environ.get("VERCEL") == "1"


def _default_base_data_dir() -> Path:
    if _is_vercel():
        return Path("/tmp/contractmind")
    return BACKEND_ROOT / "data"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(BACKEND_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    APP_NAME: str = "ContractMind v2.0"
    APP_VERSION: str = "2.0.0"
    APP_ENV: str = "development"
    SECRET_KEY: str = "contractmind-dev-secret-change-in-production"

    VERCEL: bool = _is_vercel()

    DEFAULT_LLM_PROVIDER: str = "gemini"
    DEFAULT_LLM_MODEL: str = "gemini-2.5-flash"
    GEMINI_API_KEY: str = ""
    OPENAI_API_KEY: str = ""
    ANTHROPIC_API_KEY: str = ""
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "qwen3.5:4b"

    DATABASE_URL: str = ""
    UPLOAD_DIR: str = ""
    CHROMA_PERSIST_DIR: str = ""
    EXPORT_DIR: str = ""

    def model_post_init(self, __context: object) -> None:
        base_dir = _default_base_data_dir()
        if not self.UPLOAD_DIR or self.VERCEL:
            self.UPLOAD_DIR = str(base_dir / "uploads")
        if not self.CHROMA_PERSIST_DIR or self.VERCEL:
            self.CHROMA_PERSIST_DIR = str(base_dir / "chroma")
        if not self.EXPORT_DIR or self.VERCEL:
            self.EXPORT_DIR = str(base_dir / "exports")
        if not self.DATABASE_URL or self.VERCEL:
            db_path = (base_dir / "contractmind.db").as_posix()
            self.DATABASE_URL = f"sqlite+aiosqlite:///{db_path}"

        for directory in (base_dir, Path(self.UPLOAD_DIR), Path(self.CHROMA_PERSIST_DIR), Path(self.EXPORT_DIR)):
            directory.mkdir(parents=True, exist_ok=True)


settings = Settings()
