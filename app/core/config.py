import os
from dataclasses import dataclass
from functools import lru_cache
from urllib.parse import urlparse

from dotenv import load_dotenv

load_dotenv()

DEFAULT_DATABASE_URL = "postgresql://cloud_compare:nitsan123@localhost:5432/cloud_compare"
DEFAULT_SQLITE_FALLBACK_URL = "sqlite+aiosqlite:////tmp/cloud_compare.db"


def _normalize_database_url(url: str) -> str:
    if url.startswith("postgresql://") and "+asyncpg" not in url:
        return url.replace("postgresql://", "postgresql+asyncpg://", 1)
    return url


def _allows_sqlite_fallback(url: str) -> bool:
    parsed = urlparse(url)
    return parsed.scheme.startswith("postgresql") and parsed.hostname in {
        "localhost",
        "127.0.0.1",
    }


@dataclass(frozen=True)
class Settings:
    database_url: str
    database_url_is_default: bool
    database_url_allows_fallback: bool
    sqlite_fallback_url: str
    ollama_base_url: str
    ollama_model: str


@lru_cache
def get_settings() -> Settings:
    env_database_url = os.getenv("DATABASE_URL")
    url = env_database_url or DEFAULT_DATABASE_URL
    base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/")
    model = os.getenv("OLLAMA_MODEL", "gpt-oss:120b-cloud")

    return Settings(
        database_url=_normalize_database_url(url),
        database_url_is_default=env_database_url is None,
        database_url_allows_fallback=_allows_sqlite_fallback(url),
        sqlite_fallback_url=DEFAULT_SQLITE_FALLBACK_URL,
        ollama_base_url=base_url,
        ollama_model=model,
    )
