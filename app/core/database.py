import asyncio
import logging
from collections.abc import AsyncGenerator
from typing import Annotated

from fastapi import Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_settings
from app.models import Base

logger = logging.getLogger(__name__)

FALLBACK_DATABASE_URL = "sqlite+aiosqlite:////tmp/cloud_compare.db"

engine: AsyncEngine | None = None
async_session_factory = async_sessionmaker(
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)
_init_lock = asyncio.Lock()
_is_initialized = False


def _build_engine(database_url: str) -> AsyncEngine:
    return create_async_engine(
        database_url,
        echo=False,
        future=True,
    )


def _is_local_postgres(database_url: str) -> bool:
    lowered = database_url.lower()
    return lowered.startswith("postgresql+") and any(
        host in lowered for host in ("@localhost", "@127.0.0.1", "@[::1]")
    )


async def _configure_engine(database_url: str, *, create_schema: bool) -> AsyncEngine:
    candidate_engine = _build_engine(database_url)
    try:
        async with candidate_engine.begin() as connection:
            if create_schema:
                await connection.run_sync(Base.metadata.create_all)
            else:
                await connection.execute(text("SELECT 1"))
    except Exception:
        await candidate_engine.dispose()
        raise
    return candidate_engine


async def initialize_database() -> None:
    global engine, _is_initialized

    if _is_initialized:
        return

    async with _init_lock:
        if _is_initialized:
            return

        settings = get_settings()
        configured_url = settings.database_url

        try:
            active_engine = await _configure_engine(
                configured_url,
                create_schema=False,
            )
        except Exception:
            if not _is_local_postgres(configured_url):
                raise

            logger.warning(
                "Configured database %s is unavailable; falling back to %s",
                configured_url,
                FALLBACK_DATABASE_URL,
            )
            active_engine = await _configure_engine(
                FALLBACK_DATABASE_URL,
                create_schema=True,
            )

        engine = active_engine
        async_session_factory.configure(bind=engine)
        _is_initialized = True


async def dispose_database() -> None:
    global engine, _is_initialized

    if engine is not None:
        await engine.dispose()
        engine = None
    _is_initialized = False


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
