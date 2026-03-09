import logging
from collections.abc import AsyncGenerator
from typing import Annotated

from fastapi import Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_settings, is_local_postgres_url
from app.models import Base

logger = logging.getLogger(__name__)
settings = get_settings()


def create_db_engine(url: str) -> AsyncEngine:
    return create_async_engine(
        url,
        echo=False,
        future=True,
    )


def create_session_factory(db_engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(
        db_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False,
    )


active_database_url = settings.database_url
engine = create_db_engine(active_database_url)
async_session_factory = create_session_factory(engine)


def get_database_url() -> str:
    return active_database_url


def _configure_database(url: str) -> None:
    global active_database_url, engine, async_session_factory
    active_database_url = url
    engine = create_db_engine(url)
    async_session_factory = create_session_factory(engine)


async def _probe_database_url(url: str) -> Exception | None:
    probe_engine = create_db_engine(url)
    try:
        async with probe_engine.connect() as connection:
            await connection.execute(text("SELECT 1"))
        return None
    except Exception as exc:
        return exc
    finally:
        await probe_engine.dispose()


async def resolve_database_url() -> str:
    configured_url = get_settings().database_url
    connection_error = await _probe_database_url(configured_url)
    if connection_error is None:
        return configured_url

    if not is_local_postgres_url(configured_url):
        raise connection_error

    fallback_url = get_settings().sqlite_fallback_url
    logger.warning(
        "Configured database is unavailable; falling back to SQLite at %s",
        fallback_url,
    )
    return fallback_url


async def initialize_database() -> str:
    selected_url = await resolve_database_url()
    if selected_url != active_database_url:
        await engine.dispose()
        _configure_database(selected_url)

    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    return active_database_url


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
