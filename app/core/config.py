import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

DEFAULT_DATABASE_URL = "postgresql://cloud_compare:nitsan123@localhost:5432/cloud_compare"
SQLITE_FALLBACK_URL = f"sqlite+aiosqlite:///{Path(__file__).resolve().parents[2] / 'cloud_compare.db'}"


def _normalize_database_url(url: str) -> str:
    if url.startswith("postgresql://") and "+asyncpg" not in url:
        return url.replace("postgresql://", "postgresql+asyncpg://", 1)
    return url


def is_sqlite_url(url: str) -> bool:
    return url.startswith("sqlite")


@dataclass(frozen=True)
class Settings:
    database_url: str
    sqlite_fallback_url: str
    ollama_base_url: str
    ollama_model: str


def get_settings() -> Settings:
    url = os.getenv("DATABASE_URL", DEFAULT_DATABASE_URL)
    base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/")
    model = os.getenv("OLLAMA_MODEL", "gpt-oss:120b-cloud")
    return Settings(
        database_url=_normalize_database_url(url),
        sqlite_fallback_url=SQLITE_FALLBACK_URL,
        ollama_base_url=base_url,
        ollama_model=model,
    )
