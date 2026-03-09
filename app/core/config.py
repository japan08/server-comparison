import os
from pathlib import Path
from urllib.parse import urlparse

from dotenv import load_dotenv

load_dotenv()

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DATABASE_URL = "postgresql://cloud_compare:nitsan123@localhost:5432/cloud_compare"
DEFAULT_SQLITE_PATH = PROJECT_ROOT / "cloud_compare.db"


def normalize_database_url(url: str) -> str:
    if url.startswith("postgresql://") and "+asyncpg" not in url:
        return url.replace("postgresql://", "postgresql+asyncpg://", 1)
    return url


def is_local_postgres_url(url: str) -> bool:
    normalized_url = normalize_database_url(url)
    if not normalized_url.startswith("postgresql+asyncpg://"):
        return False
    return urlparse(normalized_url).hostname in {"localhost", "127.0.0.1"}


def get_sqlite_fallback_url(path: Path | None = None) -> str:
    db_path = (path or DEFAULT_SQLITE_PATH).resolve()
    return f"sqlite+aiosqlite:///{db_path}"


def get_settings() -> object:
    url = os.getenv("DATABASE_URL", DEFAULT_DATABASE_URL)
    base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/")
    model = os.getenv("OLLAMA_MODEL", "gpt-oss:120b-cloud")

    class _Settings:
        database_url: str = normalize_database_url(url)
        sqlite_fallback_url: str = get_sqlite_fallback_url()
        ollama_base_url: str = base_url
        ollama_model: str = model

    return _Settings()
