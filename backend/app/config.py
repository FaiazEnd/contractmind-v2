"""Application configuration with Vercel serverless path fallback."""
from __future__ import annotations

import os
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


BACKEND_ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    """Runtime settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=str(BACKEND_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    APP_NAME: str = "ContractMind v2.0"
    APP_VERSION: str = "2.0.0"
    VERCEL: bool = os.getenv("VERCEL", "0") == "1"

    DEFAULT_LLM_PROVIDER: str = "gemini"
    DEFAULT_LLM_MODEL: str = "gemini-2.5-flash"

    GEMINI_API_KEY: str = ""
    OPENAI_API_KEY: str = ""
    ANTHROPIC_API_KEY: str = ""
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "qwen3.5:4b"

    SECRET_KEY: str = "contractmind-local-dev-secret-change-in-prod"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440

    @property
    def DATA_DIR(self) -> Path:
        base = Path("/tmp/contractmind_data") if self.VERCEL else (BACKEND_ROOT / "data")
        base.mkdir(parents=True, exist_ok=True)
        return base

    @property
    def UPLOAD_DIR(self) -> Path:
        path = self.DATA_DIR / "uploads"
        path.mkdir(parents=True, exist_ok=True)
        return path

    @property
    def CHROMA_PERSIST_DIR(self) -> str:
        path = self.DATA_DIR / "chroma"
        path.mkdir(parents=True, exist_ok=True)
        return str(path)

    @property
    def DATABASE_URL(self) -> str:
        if self.VERCEL:
            return "sqlite+aiosqlite:////tmp/contractmind.db"
        db_path = self.DATA_DIR / "contractmind.db"
        return f"sqlite+aiosqlite:///{db_path.as_posix()}"

    @property
    def STATIC_DIR(self) -> Path:
        return BACKEND_ROOT / "static"


settings = Settings()
