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


def _create_engine(url: str) -> AsyncEngine:
    connect_args = {"check_same_thread": False} if url.startswith("sqlite+aiosqlite://") else {}
    return create_async_engine(
        url,
        echo=False,
        future=True,
        connect_args=connect_args,
    )


def _create_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False,
    )


engine = _create_engine(get_settings().database_url)
async_session_factory = _create_session_factory(engine)


def _configure_database(url: str) -> None:
    global engine, async_session_factory
    engine = _create_engine(url)
    async_session_factory = _create_session_factory(engine)


async def _create_schema() -> None:
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)


async def initialize_database() -> None:
    configured_url = get_settings().database_url
    try:
        async with engine.begin() as connection:
            await connection.execute(text("SELECT 1"))
        await _create_schema()
    except Exception:
        if configured_url.startswith("sqlite+aiosqlite://"):
            raise

        await engine.dispose()
        SQLITE_FALLBACK_PATH.parent.mkdir(parents=True, exist_ok=True)
        _configure_database(SQLITE_FALLBACK_URL)
        await _create_schema()


async def dispose_database() -> None:
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
