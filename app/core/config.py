import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent.parent
DEFAULT_DATABASE_URL = f"sqlite+aiosqlite:///{(BASE_DIR / 'cloud_compare.db').as_posix()}"


def _normalize_database_url(url: str) -> str:
    if url.startswith("postgresql://") and "+asyncpg" not in url:
        return url.replace("postgresql://", "postgresql+asyncpg://", 1)
    return url


def get_settings() -> object:
    url = os.getenv("DATABASE_URL", DEFAULT_DATABASE_URL)
    base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/")
    model = os.getenv("OLLAMA_MODEL", "gpt-oss:120b-cloud")

    class _Settings:
        database_url: str = _normalize_database_url(url)
        ollama_base_url: str = base_url
        ollama_model: str = model

    return _Settings()
