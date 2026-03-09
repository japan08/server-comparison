import logging
from collections.abc import AsyncGenerator
from typing import Annotated

from fastapi import Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_settings
from app.models import Base

logger = logging.getLogger(__name__)
settings = get_settings()


def _create_engine(url: str) -> AsyncEngine:
    return create_async_engine(
        url,
        echo=False,
        future=True,
    )


def _create_session_factory(current_engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(
        current_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False,
    )


engine = _create_engine(settings.database_url)
async_session_factory = _create_session_factory(engine)


async def _use_fallback_database() -> None:
    global engine, async_session_factory

    fallback_engine = _create_engine(settings.fallback_database_url)
    async with fallback_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    await engine.dispose()
    engine = fallback_engine
    async_session_factory = _create_session_factory(engine)


async def initialize_database() -> None:
    try:
        async with engine.begin() as conn:
            await conn.execute(text("SELECT 1"))
    except Exception as exc:
        logger.warning(
            "Configured database %s is unavailable (%s). Falling back to %s.",
            settings.database_url,
            exc,
            settings.fallback_database_url,
        )
        await _use_fallback_database()


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
