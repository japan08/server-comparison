import asyncio
import logging
from collections.abc import AsyncGenerator
from pathlib import Path
from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_settings
from app.models import Base

LOGGER = logging.getLogger(__name__)
SQLITE_FALLBACK_PATH = Path(__file__).resolve().parents[2] / "cloud_compare.db"
SQLITE_FALLBACK_URL = f"sqlite+aiosqlite:///{SQLITE_FALLBACK_PATH}"

primary_engine = create_async_engine(
    get_settings().database_url,
    echo=False,
    future=True,
)
fallback_engine = create_async_engine(
    SQLITE_FALLBACK_URL,
    echo=False,
    future=True,
)

_engine_lock = asyncio.Lock()
_active_engine: AsyncEngine | None = None
_active_session_factory: async_sessionmaker[AsyncSession] | None = None


def _build_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False,
    )


def _should_fallback(exc: Exception) -> bool:
    current: BaseException | None = exc
    while current is not None:
        if isinstance(current, (ConnectionRefusedError, OSError, TimeoutError)):
            return True
        current = current.__cause__ or current.__context__

    message = str(exc).lower()
    return any(
        marker in message
        for marker in (
            "connection refused",
            "could not connect",
            "failed to connect",
            "connection timeout",
            "name or service not known",
            "temporary failure in name resolution",
        )
    )


async def _activate_engine(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    session_factory = _build_session_factory(engine)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    return session_factory


async def init_database() -> None:
    global _active_engine, _active_session_factory

    if _active_engine is not None and _active_session_factory is not None:
        return

    async with _engine_lock:
        if _active_engine is not None and _active_session_factory is not None:
            return

        try:
            _active_session_factory = await _activate_engine(primary_engine)
            _active_engine = primary_engine
        except Exception as exc:
            if not _should_fallback(exc):
                raise

            LOGGER.warning(
                "Configured database is unavailable; falling back to SQLite at %s",
                SQLITE_FALLBACK_PATH,
            )
            _active_session_factory = await _activate_engine(fallback_engine)
            _active_engine = fallback_engine


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    await init_database()

    if _active_session_factory is None:
        raise RuntimeError("Database session factory was not initialized")

    async with _active_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


DbSession = Annotated[AsyncSession, Depends(get_db)]
