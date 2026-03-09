import asyncio
from collections.abc import AsyncGenerator
from typing import Annotated

from fastapi import Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_settings
from app.models import Base

engine: AsyncEngine | None = None
async_session_factory: async_sessionmaker[AsyncSession] | None = None
_db_init_lock = asyncio.Lock()


def _build_engine(database_url: str) -> AsyncEngine:
    return create_async_engine(database_url, echo=False, future=True)


def _build_session_factory(bound_engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(
        bound_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False,
    )


async def initialize_database() -> None:
    global engine, async_session_factory

    if engine is not None and async_session_factory is not None:
        return

    async with _db_init_lock:
        if engine is not None and async_session_factory is not None:
            return

        settings = get_settings()
        primary_engine = _build_engine(settings.database_url)

        try:
            async with primary_engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
            active_engine = primary_engine
        except Exception:
            await primary_engine.dispose()
            if not settings.local_database_url:
                raise
            active_engine = _build_engine(settings.sqlite_fallback_url)

        async with active_engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        engine = active_engine
        async_session_factory = _build_session_factory(active_engine)


async def close_database() -> None:
    global engine, async_session_factory

    if engine is not None:
        await engine.dispose()

    engine = None
    async_session_factory = None


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    if async_session_factory is None:
        await initialize_database()

    assert async_session_factory is not None
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
