from collections.abc import AsyncGenerator
from pathlib import Path
from typing import Annotated
from urllib.parse import urlparse

from fastapi import Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_settings
from app.models import Base

FALLBACK_SQLITE_URL = f"sqlite+aiosqlite:///{Path('/tmp/cloud_compare.db')}"


def _create_engine(url: str) -> AsyncEngine:
    return create_async_engine(
        url,
        echo=False,
        future=True,
    )


def _create_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False,
    )


def _is_local_postgres_url(url: str) -> bool:
    parsed = urlparse(url)
    return parsed.scheme.startswith("postgresql") and (parsed.hostname in {"localhost", "127.0.0.1"})


engine = _create_engine(get_settings().database_url)
async_session_factory = _create_session_factory(engine)


async def initialize_database() -> None:
    global engine, async_session_factory

    settings = get_settings()
    configured_url = settings.database_url

    try:
        async with engine.connect() as connection:
            await connection.execute(text("SELECT 1"))
        return
    except Exception:
        if not _is_local_postgres_url(configured_url):
            raise

    await engine.dispose()
    engine = _create_engine(FALLBACK_SQLITE_URL)
    async_session_factory = _create_session_factory(engine)

    # Local automation should still boot cleanly even without Postgres.
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
