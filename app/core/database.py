from collections.abc import AsyncGenerator
from typing import Annotated

from fastapi import Depends
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, OperationalError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_settings
from app.models import Base

settings = get_settings()


def _build_engine(database_url: str):
    return create_async_engine(
        database_url,
        echo=False,
        future=True,
    )


def _build_session_factory(target_engine):
    return async_sessionmaker(
        target_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False,
    )


def _can_fallback_to_sqlite(database_url: str) -> bool:
    return database_url.startswith("postgresql+asyncpg://") and (
        "@localhost:" in database_url or "@127.0.0.1:" in database_url
    )


engine = _build_engine(settings.database_url)
async_session_factory = _build_session_factory(engine)


async def _ensure_schema(target_engine) -> None:
    async with target_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def initialize_database() -> None:
    global engine, async_session_factory

    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        await _ensure_schema(engine)
    except (ConnectionError, DBAPIError, OSError, OperationalError):
        if not _can_fallback_to_sqlite(settings.database_url):
            raise

        await engine.dispose()
        engine = _build_engine(settings.sqlite_fallback_url)
        async_session_factory = _build_session_factory(engine)
        await _ensure_schema(engine)


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
