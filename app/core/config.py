import os
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

from dotenv import load_dotenv

load_dotenv()

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DATABASE_URL = "postgresql://cloud_compare:nitsan123@localhost:5432/cloud_compare"
DEFAULT_SQLITE_DATABASE_PATH = REPO_ROOT / "cloud_compare.db"


def _normalize_database_url(url: str) -> str:
    if url.startswith("postgresql://") and "+asyncpg" not in url:
        return url.replace("postgresql://", "postgresql+asyncpg://", 1)
    return url


def _sqlite_database_url(path: Path) -> str:
    return f"sqlite+aiosqlite:///{path}"


def _is_local_postgres_url(url: str) -> bool:
    normalized_url = _normalize_database_url(url)
    if not normalized_url.startswith("postgresql"):
        return False
    return urlparse(normalized_url).hostname in {"localhost", "127.0.0.1", "::1"}


@dataclass(frozen=True)
class Settings:
    database_url: str
    sqlite_database_url: str
    ollama_base_url: str
    ollama_model: str

    @property
    def should_fallback_to_sqlite(self) -> bool:
        return _is_local_postgres_url(self.database_url)


def get_settings() -> Settings:
    database_url = os.getenv("DATABASE_URL", DEFAULT_DATABASE_URL)
    sqlite_database_path = Path(
        os.getenv("SQLITE_DATABASE_PATH", str(DEFAULT_SQLITE_DATABASE_PATH))
    )
    base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/")
    model = os.getenv("OLLAMA_MODEL", "gpt-oss:120b-cloud")

    return Settings(
        database_url=_normalize_database_url(database_url),
        sqlite_database_url=_sqlite_database_url(sqlite_database_path),
        ollama_base_url=base_url,
        ollama_model=model,
    )
