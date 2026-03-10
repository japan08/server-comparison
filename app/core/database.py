from collections.abc import AsyncGenerator
from typing import Annotated

from fastapi import Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import DEFAULT_DATABASE_URL, _normalize_database_url, get_settings
from app.models import Base

FALLBACK_SQLITE_URL = "sqlite+aiosqlite:////tmp/cloud_compare.db"

settings = get_settings()
default_database_url = _normalize_database_url(DEFAULT_DATABASE_URL)
active_database_url = settings.database_url


def _create_engine(database_url: str) -> AsyncEngine:
    return create_async_engine(
        database_url,
        echo=False,
        future=True,
    )


def _create_session_factory(bind: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(
        bind,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False,
    )


engine = _create_engine(active_database_url)
async_session_factory = _create_session_factory(engine)


async def initialize_database() -> None:
    global active_database_url, async_session_factory, engine

    if active_database_url.startswith("sqlite+aiosqlite://"):
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        return

    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
    except Exception:
        if active_database_url != default_database_url:
            raise

        fallback_engine = _create_engine(FALLBACK_SQLITE_URL)
        async with fallback_engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        await engine.dispose()
        engine = fallback_engine
        async_session_factory = _create_session_factory(engine)
        active_database_url = FALLBACK_SQLITE_URL


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
