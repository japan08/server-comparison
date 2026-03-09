import asyncio
import logging
from collections.abc import AsyncGenerator
from typing import Annotated

from fastapi import Depends
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_settings
from app.models import Base

logger = logging.getLogger(__name__)

engine = None
async_session_factory = None
_init_lock = asyncio.Lock()


def _build_session_factory(db_engine):
    return async_sessionmaker(
        db_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False,
    )


async def _create_engine_and_schema(database_url: str):
    db_engine = create_async_engine(
        database_url,
        echo=False,
        future=True,
    )
    try:
        async with db_engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        return db_engine
    except Exception:
        await db_engine.dispose()
        raise


async def initialize_database() -> None:
    global engine, async_session_factory

    if async_session_factory is not None:
        return

    async with _init_lock:
        if async_session_factory is not None:
            return

        settings = get_settings()
        try:
            engine = await _create_engine_and_schema(settings.database_url)
        except (OSError, SQLAlchemyError) as exc:
            if not settings.use_sqlite_fallback:
                raise
            logger.warning(
                "Configured database %s is unavailable (%s); falling back to %s",
                settings.database_url,
                exc,
                settings.sqlite_fallback_url,
            )
            engine = await _create_engine_and_schema(settings.sqlite_fallback_url)

        async_session_factory = _build_session_factory(engine)


async def close_database() -> None:
    global engine, async_session_factory

    if engine is not None:
        await engine.dispose()
    engine = None
    async_session_factory = None


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    if async_session_factory is None:
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
