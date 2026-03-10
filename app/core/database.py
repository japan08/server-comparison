import logging
from collections.abc import AsyncGenerator
from pathlib import Path
from typing import Annotated

from fastapi import Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_settings
from app.models import Base

logger = logging.getLogger(__name__)
FALLBACK_SQLITE_URL = f"sqlite+aiosqlite:///{Path('/tmp/cloud_compare.db')}"


def _build_engine(database_url: str) -> AsyncEngine:
    return create_async_engine(
        database_url,
        echo=False,
        future=True,
    )


def _build_session_factory(
    database_engine: AsyncEngine,
) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(
        database_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False,
    )


settings = get_settings()
engine = _build_engine(settings.database_url)
async_session_factory = _build_session_factory(engine)


async def initialize_database() -> None:
    """Prefer the configured database but fall back to SQLite when it is unavailable."""
    global engine, async_session_factory

    try:
        async with engine.begin() as connection:
            await connection.execute(text("SELECT 1"))
        return
    except Exception as exc:
        configured_url = settings.database_url
        if configured_url.startswith("sqlite+"):
            raise

        logger.warning(
            "Configured database is unavailable (%s); falling back to SQLite at %s",
            exc,
            FALLBACK_SQLITE_URL,
        )
        await engine.dispose()

    engine = _build_engine(FALLBACK_SQLITE_URL)
    async_session_factory = _build_session_factory(engine)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)


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
