from collections.abc import AsyncGenerator
from pathlib import Path
from typing import Annotated

from fastapi import Depends
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import DEFAULT_DATABASE_URL, get_settings
from app.models import Base

SQLITE_FALLBACK_PATH = Path("/tmp/cloud_compare.db")
SQLITE_FALLBACK_URL = f"sqlite+aiosqlite:///{SQLITE_FALLBACK_PATH}"
NORMALIZED_DEFAULT_DATABASE_URL = DEFAULT_DATABASE_URL.replace(
    "postgresql://",
    "postgresql+asyncpg://",
    1,
)


def _build_engine(
    database_url: str,
) -> tuple[AsyncEngine, async_sessionmaker[AsyncSession]]:
    engine = create_async_engine(
        database_url,
        echo=False,
        future=True,
    )
    session_factory = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False,
    )
    return engine, session_factory


def _is_local_postgres(database_url: str) -> bool:
    if not database_url.startswith("postgresql"):
        return False

    try:
        parsed = make_url(database_url)
    except Exception:
        return False

    host = (parsed.host or "").lower()
    return host in {"localhost", "127.0.0.1"} or database_url == NORMALIZED_DEFAULT_DATABASE_URL


selected_database_url = get_settings().database_url
engine, async_session_factory = _build_engine(selected_database_url)


async def _create_schema() -> None:
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)


async def initialize_database() -> None:
    global engine, async_session_factory, selected_database_url

    try:
        async with engine.connect() as connection:
            await connection.execute(text("SELECT 1"))
    except Exception:
        if not _is_local_postgres(selected_database_url):
            raise

        await engine.dispose()
        SQLITE_FALLBACK_PATH.parent.mkdir(parents=True, exist_ok=True)
        selected_database_url = SQLITE_FALLBACK_URL
        engine, async_session_factory = _build_engine(selected_database_url)

    await _create_schema()


async def close_database() -> None:
    await engine.dispose()


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


DbSession = Annotated[AsyncSession, Depends(get_db)]
