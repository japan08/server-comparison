import logging
from collections.abc import AsyncGenerator
from pathlib import Path
from typing import Annotated

from fastapi import Depends
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_settings
from app.models import Base

logger = logging.getLogger(__name__)
SQLITE_FALLBACK_PATH = Path("/tmp/cloud_compare.db")
SQLITE_FALLBACK_URL = f"sqlite+aiosqlite:///{SQLITE_FALLBACK_PATH}"


def _create_engine(database_url: str) -> AsyncEngine:
    return create_async_engine(
        database_url,
        echo=False,
        future=True,
    )


def _create_session_factory(db_engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(
        db_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False,
    )


_active_database_url = get_settings().database_url
engine = _create_engine(_active_database_url)
async_session_factory = _create_session_factory(engine)


async def initialize_database() -> None:
    global _active_database_url, async_session_factory, engine

    try:
        async with engine.connect() as connection:
            await connection.execute(text("SELECT 1"))
    except (OSError, SQLAlchemyError) as exc:
        if _active_database_url.startswith("sqlite+aiosqlite://"):
            raise

        fallback_engine = _create_engine(SQLITE_FALLBACK_URL)
        SQLITE_FALLBACK_PATH.parent.mkdir(parents=True, exist_ok=True)
        async with fallback_engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

        await engine.dispose()
        engine = fallback_engine
        async_session_factory = _create_session_factory(engine)
        logger.warning(
            "Configured database %s is unavailable (%s); falling back to %s",
            _active_database_url,
            exc,
            SQLITE_FALLBACK_URL,
        )
        _active_database_url = SQLITE_FALLBACK_URL
        return

    if _active_database_url.startswith("sqlite+aiosqlite://"):
        SQLITE_FALLBACK_PATH.parent.mkdir(parents=True, exist_ok=True)
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
