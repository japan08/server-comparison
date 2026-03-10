import logging
from collections.abc import AsyncGenerator
from typing import Annotated

from fastapi import Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_settings
from app.models import Base

logger = logging.getLogger(__name__)

SQLITE_FALLBACK_URL = "sqlite+aiosqlite:////tmp/cloud_compare.db"


def _create_engine(database_url: str) -> AsyncEngine:
    return create_async_engine(
        database_url,
        echo=False,
        future=True,
    )


def _create_session_factory(
    db_engine: AsyncEngine,
) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(
        db_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False,
    )


engine = _create_engine(get_settings().database_url)
async_session_factory = _create_session_factory(engine)


async def _is_database_available(db_engine: AsyncEngine) -> bool:
    try:
        async with db_engine.connect() as connection:
            await connection.execute(text("SELECT 1"))
        return True
    except Exception as exc:
        logger.warning(
            "Configured database is unavailable (%s); falling back to SQLite at %s",
            exc,
            SQLITE_FALLBACK_URL,
        )
        return False


async def initialize_database() -> None:
    global engine, async_session_factory

    if await _is_database_available(engine):
        return

    await engine.dispose()
    engine = _create_engine(SQLITE_FALLBACK_URL)
    async_session_factory = _create_session_factory(engine)

    # The SQLite fallback is local-only, so create the schema on demand.
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
