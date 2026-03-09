import os
from pathlib import Path
from urllib.parse import urlparse

from dotenv import load_dotenv

load_dotenv()

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DATABASE_URL = "postgresql://cloud_compare:nitsan123@localhost:5432/cloud_compare"
DEFAULT_SQLITE_PATH = PROJECT_ROOT / "cloud_compare.db"


def _normalize_database_url(url: str) -> str:
    if url.startswith("postgresql://") and "+asyncpg" not in url:
        return url.replace("postgresql://", "postgresql+asyncpg://", 1)
    if url.startswith("sqlite:///") and "+aiosqlite" not in url:
        return url.replace("sqlite:///", "sqlite+aiosqlite:///", 1)
    return url


def _is_local_postgres_url(url: str) -> bool:
    normalized = url.replace("postgresql+asyncpg://", "postgresql://", 1)
    parsed = urlparse(normalized)
    return parsed.scheme == "postgresql" and parsed.hostname in {None, "localhost", "127.0.0.1"}


def get_settings() -> object:
    url = os.getenv("DATABASE_URL", DEFAULT_DATABASE_URL)
    base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/")
    model = os.getenv("OLLAMA_MODEL", "gpt-oss:120b-cloud")
    sqlite_fallback_url = f"sqlite:///{DEFAULT_SQLITE_PATH}"

    class _Settings:
        pass

    _Settings.database_url = _normalize_database_url(url)
    _Settings.sqlite_fallback_url = _normalize_database_url(sqlite_fallback_url)
    _Settings.use_sqlite_fallback = _is_local_postgres_url(url)
    _Settings.ollama_base_url = base_url
    _Settings.ollama_model = model

    return _Settings()
