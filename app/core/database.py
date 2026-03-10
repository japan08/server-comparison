import logging
from collections.abc import AsyncGenerator
from pathlib import Path
from typing import Annotated

from fastapi import Depends
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_settings
from app.models import Base

logger = logging.getLogger(__name__)
SQLITE_FALLBACK_PATH = Path("/tmp/cloud_compare.db")
SQLITE_FALLBACK_URL = f"sqlite+aiosqlite:///{SQLITE_FALLBACK_PATH}"


def _build_engine(database_url: str) -> AsyncEngine:
    return create_async_engine(
        database_url,
        echo=False,
        future=True,
    )


def _build_session_factory(
    bind: AsyncEngine,
) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(
        bind,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False,
    )


def _is_local_postgres_url(database_url: str) -> bool:
    parsed = make_url(database_url)
    return parsed.get_backend_name() == "postgresql" and parsed.host in {
        None,
        "localhost",
        "127.0.0.1",
    }


engine = _build_engine(get_settings().database_url)
async_session_factory = _build_session_factory(engine)
active_database_url = get_settings().database_url


async def _ensure_connection(target_engine: AsyncEngine) -> None:
    async with target_engine.connect() as connection:
        await connection.execute(text("SELECT 1"))


async def _create_schema(target_engine: AsyncEngine) -> None:
    async with target_engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)


async def initialize_database() -> None:
    global engine, async_session_factory, active_database_url

    try:
        await _ensure_connection(engine)
    except (ConnectionError, OSError, OperationalError):
        if not _is_local_postgres_url(active_database_url):
            raise

        logger.warning(
            "Database %s is unavailable; falling back to %s",
            active_database_url,
            SQLITE_FALLBACK_URL,
        )
        await engine.dispose()
        SQLITE_FALLBACK_PATH.parent.mkdir(parents=True, exist_ok=True)
        engine = _build_engine(SQLITE_FALLBACK_URL)
        async_session_factory = _build_session_factory(engine)
        active_database_url = SQLITE_FALLBACK_URL

    await _create_schema(engine)


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
