import logging
from collections.abc import AsyncGenerator
from typing import Annotated
from urllib.parse import urlparse

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_settings, is_sqlite_url
from app.models import Base

logger = logging.getLogger(__name__)
settings = get_settings()

engine: AsyncEngine
async_session_factory: async_sessionmaker[AsyncSession]
current_database_url = ""


def _configure_engine(database_url: str) -> None:
    global engine, async_session_factory, current_database_url
    engine = create_async_engine(
        database_url,
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
    current_database_url = database_url


def _can_fallback_to_sqlite(database_url: str) -> bool:
    if is_sqlite_url(database_url):
        return False
    host = urlparse(database_url).hostname
    return host in {None, "localhost", "127.0.0.1"}


async def _create_sqlite_schema() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def ensure_database_ready() -> None:
    try:
        async with engine.begin():
            pass
        if is_sqlite_url(current_database_url):
            await _create_sqlite_schema()
        return
    except Exception as exc:
        if not _can_fallback_to_sqlite(current_database_url):
            raise
        logger.warning(
            "Database unavailable at %s; falling back to local SQLite. Error: %s",
            current_database_url,
            exc,
        )
        await engine.dispose()
        _configure_engine(settings.sqlite_fallback_url)
        await _create_sqlite_schema()


_configure_engine(settings.database_url)


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
