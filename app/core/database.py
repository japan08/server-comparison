from collections.abc import AsyncGenerator
from pathlib import Path
from typing import Annotated

from fastapi import Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_settings
from app.models import Base

SQLITE_FALLBACK_PATH = Path("/tmp/cloud_compare.db")
SQLITE_FALLBACK_URL = f"sqlite+aiosqlite:///{SQLITE_FALLBACK_PATH}"

engine: AsyncEngine | None = None
async_session_factory: async_sessionmaker[AsyncSession] | None = None


def _build_engine(database_url: str) -> AsyncEngine:
    return create_async_engine(
        database_url,
        echo=False,
        future=True,
    )


def _configure_engine(database_url: str) -> None:
    global engine, async_session_factory
    engine = _build_engine(database_url)
    async_session_factory = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False,
    )


_configure_engine(get_settings().database_url)


async def _can_connect(target_engine: AsyncEngine) -> bool:
    try:
        async with target_engine.connect() as connection:
            await connection.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


async def initialize_database() -> None:
    """Validate the configured database and fall back to SQLite if needed."""
    global engine

    if engine is None:
        _configure_engine(get_settings().database_url)

    assert engine is not None

    if await _can_connect(engine):
        return

    configured_url = get_settings().database_url
    if configured_url == SQLITE_FALLBACK_URL:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        return

    await engine.dispose()
    _configure_engine(SQLITE_FALLBACK_URL)
    assert engine is not None
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)


async def dispose_database() -> None:
    if engine is not None:
        await engine.dispose()


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    if async_session_factory is None:
        raise RuntimeError("Database session factory is not initialized")

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
