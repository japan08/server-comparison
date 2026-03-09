import asyncio
from collections.abc import AsyncGenerator
from pathlib import Path
from typing import Annotated
from urllib.parse import urlparse

from fastapi import Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_settings
from app.models import Base

FALLBACK_SQLITE_PATH = Path("/tmp/cloud_compare.db")
FALLBACK_SQLITE_URL = f"sqlite+aiosqlite:///{FALLBACK_SQLITE_PATH}"

_database_init_lock = asyncio.Lock()
_database_initialized = False


def _build_engine(database_url: str) -> AsyncEngine:
    return create_async_engine(
        database_url,
        echo=False,
        future=True,
        pool_pre_ping=True,
    )


def _build_session_factory(
    db_engine: AsyncEngine,
) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(
        db_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False,
    )


engine = _build_engine(get_settings().database_url)
async_session_factory = _build_session_factory(engine)


def _can_fallback_to_sqlite(database_url: str) -> bool:
    if not database_url.startswith(("postgresql://", "postgresql+asyncpg://")):
        return False

    hostname = urlparse(database_url).hostname
    return hostname in {None, "localhost", "127.0.0.1", "::1"}


async def _verify_connection(db_engine: AsyncEngine) -> None:
    async with db_engine.connect() as connection:
        await connection.execute(text("SELECT 1"))


async def _switch_to_sqlite_fallback() -> None:
    global engine, async_session_factory

    FALLBACK_SQLITE_PATH.parent.mkdir(parents=True, exist_ok=True)

    fallback_engine = _build_engine(FALLBACK_SQLITE_URL)
    async with fallback_engine.begin() as connection:
        # The fallback database is only for local smoke tests, so model metadata is enough.
        await connection.run_sync(Base.metadata.create_all)

    await engine.dispose()
    engine = fallback_engine
    async_session_factory = _build_session_factory(engine)


async def initialize_database() -> None:
    global _database_initialized

    if _database_initialized:
        return

    async with _database_init_lock:
        if _database_initialized:
            return

        database_url = get_settings().database_url
        try:
            await _verify_connection(engine)
        except Exception:
            if not _can_fallback_to_sqlite(database_url):
                raise
            await _switch_to_sqlite_fallback()

        _database_initialized = True


async def close_database() -> None:
    global _database_initialized

    await engine.dispose()
    _database_initialized = False


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    await initialize_database()

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
