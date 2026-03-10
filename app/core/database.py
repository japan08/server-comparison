from collections.abc import AsyncGenerator
from pathlib import Path
from typing import Annotated
from urllib.parse import urlparse

from fastapi import Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_settings
from app.models import Base

SQLITE_FALLBACK_PATH = Path("/tmp/cloud_compare.db")
SQLITE_FALLBACK_URL = f"sqlite+aiosqlite:///{SQLITE_FALLBACK_PATH}"


def _build_engine(database_url: str) -> AsyncEngine:
    return create_async_engine(
        database_url,
        echo=False,
        future=True,
    )


def _build_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False,
    )


settings = get_settings()
configured_database_url = settings.database_url
active_database_url = configured_database_url
engine = _build_engine(active_database_url)
async_session_factory = _build_session_factory(engine)
_database_initialized = False


def _should_use_sqlite_fallback(database_url: str) -> bool:
    parsed = urlparse(database_url)
    return parsed.scheme.startswith("postgresql") and parsed.hostname in {"localhost", "127.0.0.1"}


async def _ping_database(target_engine: AsyncEngine) -> None:
    async with target_engine.connect() as connection:
        await connection.execute(text("SELECT 1"))


async def _create_schema(target_engine: AsyncEngine) -> None:
    async with target_engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)


async def initialize_database() -> None:
    global active_database_url, async_session_factory, engine, _database_initialized

    if _database_initialized:
        return

    try:
        await _ping_database(engine)
    except Exception:
        if not _should_use_sqlite_fallback(configured_database_url):
            raise

        await engine.dispose()
        engine = _build_engine(SQLITE_FALLBACK_URL)
        async_session_factory = _build_session_factory(engine)
        active_database_url = SQLITE_FALLBACK_URL
        await _create_schema(engine)
        _database_initialized = True
        return

    _database_initialized = True


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
