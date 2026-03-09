import logging
from collections.abc import AsyncGenerator
from pathlib import Path
from typing import Annotated

from fastapi import Depends
from sqlalchemy.engine import make_url
from sqlalchemy.exc import DBAPIError, OperationalError
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_settings
from app.models import Base

logger = logging.getLogger(__name__)
SQLITE_FALLBACK_URL = f"sqlite+aiosqlite:///{Path('/tmp/cloud_compare.db')}"

engine: AsyncEngine | None = None
async_session_factory: async_sessionmaker[AsyncSession] | None = None


def _build_engine(url: str) -> AsyncEngine:
    return create_async_engine(url, echo=False, future=True)


def _build_session_factory(
    current_engine: AsyncEngine,
) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(
        current_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False,
    )


def _should_fallback_to_sqlite(url: str) -> bool:
    parsed = make_url(url)
    return parsed.drivername.startswith("postgresql") and parsed.host in {
        None,
        "",
        "localhost",
        "127.0.0.1",
    }


async def _configure_database(url: str) -> None:
    global engine, async_session_factory

    if engine is not None:
        await engine.dispose()

    engine = _build_engine(url)
    async_session_factory = _build_session_factory(engine)


async def _create_schema() -> None:
    if engine is None:
        raise RuntimeError("Database engine is not configured.")

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def init_database() -> None:
    global async_session_factory

    if async_session_factory is not None:
        return

    primary_url = get_settings().database_url
    await _configure_database(primary_url)

    try:
        await _create_schema()
    except (OperationalError, DBAPIError, OSError) as exc:
        if not _should_fallback_to_sqlite(primary_url):
            raise

        logger.warning(
            "Primary database is unavailable (%s); falling back to local SQLite.",
            exc.__class__.__name__,
        )
        await _configure_database(SQLITE_FALLBACK_URL)
        await _create_schema()


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    await init_database()
    if async_session_factory is None:
        raise RuntimeError("Database session factory is not initialized.")

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
