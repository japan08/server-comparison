import asyncio
import logging
from collections.abc import AsyncGenerator
from typing import Annotated

from fastapi import Depends
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_fallback_database_url, get_settings
from app.models import Base

logger = logging.getLogger(__name__)

_INITIALIZATION_LOCK = asyncio.Lock()
_initialized = False
_active_database_url = ""
engine: AsyncEngine
async_session_factory: async_sessionmaker[AsyncSession]


def _configure_engine(url: str) -> None:
    global _active_database_url, _initialized, async_session_factory, engine

    engine = create_async_engine(
        url,
        echo=False,
        future=True,
    )
    async_session_factory = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False,
    )
    _active_database_url = url
    _initialized = False


def _is_local_postgres_url(url: str) -> bool:
    parsed = make_url(url)
    return parsed.get_backend_name() == "postgresql" and parsed.host in {
        None,
        "localhost",
        "127.0.0.1",
    }


async def _ping_database(candidate: AsyncEngine) -> None:
    async with candidate.connect() as connection:
        await connection.execute(text("SELECT 1"))


async def initialize_database() -> str:
    global _initialized

    if _initialized:
        return _active_database_url

    async with _INITIALIZATION_LOCK:
        if _initialized:
            return _active_database_url

        try:
            await _ping_database(engine)
        except Exception:
            if not _is_local_postgres_url(_active_database_url):
                raise

            fallback_url = get_fallback_database_url()
            logger.warning(
                "Local PostgreSQL is unavailable; falling back to SQLite at %s",
                fallback_url.removeprefix("sqlite+aiosqlite:///"),
            )
            await engine.dispose()
            _configure_engine(fallback_url)
            await _ping_database(engine)

        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

        _initialized = True
        return _active_database_url


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    return async_session_factory


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


_configure_engine(get_settings().database_url)

DbSession = Annotated[AsyncSession, Depends(get_db)]
