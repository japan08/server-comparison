import logging
from collections.abc import AsyncGenerator
from pathlib import Path
from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_settings
from app.models import Base

logger = logging.getLogger(__name__)
SQLITE_FALLBACK_PATH = Path(__file__).resolve().parents[2] / "cloud_compare.db"
SQLITE_FALLBACK_URL = f"sqlite+aiosqlite:///{SQLITE_FALLBACK_PATH}"


def _make_engine(database_url: str) -> AsyncEngine:
    return create_async_engine(
        database_url,
        echo=False,
        future=True,
    )


def _make_session_factory(active_engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(
        active_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False,
    )


engine = _make_engine(get_settings().database_url)
async_session_factory = _make_session_factory(engine)


async def _can_connect(database_url: str) -> bool:
    probe_engine = _make_engine(database_url)
    try:
        async with probe_engine.begin():
            return True
    except Exception as exc:
        logger.warning("Database unavailable for %s: %s", database_url, exc)
        return False
    finally:
        await probe_engine.dispose()


async def _configure_database(database_url: str) -> None:
    global engine, async_session_factory
    await engine.dispose()
    engine = _make_engine(database_url)
    async_session_factory = _make_session_factory(engine)


async def initialize_database() -> None:
    configured_url = get_settings().database_url
    active_url = configured_url
    if not await _can_connect(configured_url):
        active_url = SQLITE_FALLBACK_URL
        logger.warning(
            "Falling back to local SQLite database at %s",
            SQLITE_FALLBACK_PATH,
        )

    await _configure_database(active_url)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


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
