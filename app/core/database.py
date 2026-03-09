import asyncio
import logging
from collections.abc import AsyncGenerator
from typing import Annotated

from fastapi import Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_settings
from app.models import Base

logger = logging.getLogger(__name__)

engine = None
async_session_factory = None
_database_init_lock = asyncio.Lock()


def _build_engine(url: str):
    return create_async_engine(
        url,
        echo=False,
        future=True,
    )


def _build_session_factory(db_engine):
    return async_sessionmaker(
        db_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False,
    )


async def _initialize_with_engine(db_engine) -> None:
    async with db_engine.begin() as conn:
        await conn.execute(text("SELECT 1"))
        await conn.run_sync(Base.metadata.create_all)


async def initialize_database() -> None:
    global engine, async_session_factory

    if engine is not None and async_session_factory is not None:
        return

    async with _database_init_lock:
        if engine is not None and async_session_factory is not None:
            return

        settings = get_settings()
        primary_engine = _build_engine(settings.database_url)

        try:
            await _initialize_with_engine(primary_engine)
            engine = primary_engine
        except Exception as exc:
            await primary_engine.dispose()
            fallback_engine = _build_engine(settings.fallback_database_url)
            await _initialize_with_engine(fallback_engine)
            engine = fallback_engine
            logger.warning(
                "Primary database unavailable, using SQLite fallback at %s: %s",
                settings.fallback_database_url,
                exc,
            )

        async_session_factory = _build_session_factory(engine)


async def dispose_database() -> None:
    global engine, async_session_factory

    if engine is not None:
        await engine.dispose()
    engine = None
    async_session_factory = None


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
