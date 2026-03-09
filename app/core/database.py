import logging
from collections.abc import AsyncGenerator
from typing import Annotated

from fastapi import Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_settings
from app.models import Base

logger = logging.getLogger(__name__)


def _create_engine(database_url: str):
    return create_async_engine(
        database_url,
        echo=False,
        future=True,
    )


def _create_session_factory(current_engine):
    return async_sessionmaker(
        current_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False,
    )


engine = _create_engine(get_settings().database_url)
async_session_factory = _create_session_factory(engine)


def _current_database_url() -> str:
    return engine.url.render_as_string(hide_password=False)


async def _set_database_url(database_url: str) -> None:
    global engine, async_session_factory

    if _current_database_url() == database_url:
        return

    await engine.dispose()
    engine = _create_engine(database_url)
    async_session_factory = _create_session_factory(engine)


async def _verify_connection() -> None:
    async with engine.connect() as connection:
        await connection.execute(text("SELECT 1"))


async def _create_sqlite_schema() -> None:
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)


async def initialize_database() -> None:
    settings = get_settings()
    await _set_database_url(settings.database_url)

    try:
        await _verify_connection()
    except Exception as exc:
        if not settings.should_fallback_to_sqlite:
            raise

        logger.warning(
            "Database %s unavailable (%s); falling back to %s",
            settings.database_url,
            exc.__class__.__name__,
            settings.sqlite_database_url,
        )
        await _set_database_url(settings.sqlite_database_url)

    if engine.url.get_backend_name() == "sqlite":
        await _create_sqlite_schema()


async def close_database() -> None:
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
