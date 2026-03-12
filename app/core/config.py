import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

DEFAULT_DATABASE_PATH = Path(__file__).resolve().parents[2] / "cloud_compare.db"
DEFAULT_DATABASE_URL = f"sqlite+aiosqlite:///{DEFAULT_DATABASE_PATH}"
LEGACY_DATABASE_URLS = {
    "postgresql://cloud_compare:nitsan123@localhost:5432/cloud_compare",
    "postgresql+asyncpg://cloud_compare:nitsan123@localhost:5432/cloud_compare",
}


def _normalize_database_url(url: str) -> str:
    if url.startswith("postgresql://") and "+asyncpg" not in url:
        return url.replace("postgresql://", "postgresql+asyncpg://", 1)
    return url


def get_settings() -> object:
    configured_url = os.getenv("DATABASE_URL", "").strip()
    if not configured_url or configured_url in LEGACY_DATABASE_URLS:
        url = DEFAULT_DATABASE_URL
    else:
        url = configured_url
    base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/")
    model = os.getenv("OLLAMA_MODEL", "gpt-oss:120b-cloud")

    class _Settings:
        database_url: str = _normalize_database_url(url)
        ollama_base_url: str = base_url
        ollama_model: str = model

    return _Settings()
