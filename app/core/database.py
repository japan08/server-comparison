import logging
from collections.abc import AsyncGenerator
from typing import Annotated

from fastapi import Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_settings
from app.models import Base

logger = logging.getLogger(__name__)
settings = get_settings()

engine = None
async_session_factory = None
active_database_url = settings.database_url
database_initialized = False


def _make_engine(database_url: str):
    return create_async_engine(
        database_url,
        echo=False,
        future=True,
    )


def _configure_session_factory(database_url: str) -> None:
    global active_database_url, engine, async_session_factory
    active_database_url = database_url
    engine = _make_engine(database_url)
    async_session_factory = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False,
    )


async def _database_is_available() -> bool:
    probe_engine = _make_engine(settings.database_url)
    try:
        async with probe_engine.connect() as connection:
            await connection.execute(text("SELECT 1"))
        return True
    except Exception as exc:
        logger.warning(
            "Primary database is unavailable (%s); using fallback SQLite database instead.",
            exc,
        )
        return False
    finally:
        await probe_engine.dispose()


async def initialize_database() -> None:
    global database_initialized
    if database_initialized:
        return

    target_database_url = settings.database_url
    if target_database_url != settings.fallback_database_url and not await _database_is_available():
        target_database_url = settings.fallback_database_url

    if async_session_factory is None or target_database_url != active_database_url:
        if engine is not None:
            await engine.dispose()
        _configure_session_factory(target_database_url)

    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    database_initialized = True


async def close_database() -> None:
    global database_initialized
    if engine is not None:
        await engine.dispose()
    database_initialized = False


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
