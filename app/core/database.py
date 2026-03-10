import logging
from collections.abc import AsyncGenerator
from pathlib import Path
from typing import Annotated
from urllib.parse import urlparse

from fastapi import Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_settings
from app.models import Base

logger = logging.getLogger(__name__)
FALLBACK_DATABASE_PATH = Path("/tmp/cloud_compare.db")
FALLBACK_DATABASE_URL = f"sqlite+aiosqlite:///{FALLBACK_DATABASE_PATH}"


def _make_engine(database_url: str):
    return create_async_engine(
        database_url,
        echo=False,
        future=True,
    )


def _should_fallback_to_sqlite(database_url: str) -> bool:
    parsed = urlparse(database_url)
    return parsed.scheme.startswith("postgresql") and parsed.hostname in {
        None,
        "localhost",
        "127.0.0.1",
    }


_database_url = get_settings().database_url
engine = _make_engine(_database_url)

async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


async def _enable_sqlite_fallback() -> None:
    global engine, _database_url

    await engine.dispose()
    FALLBACK_DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
    engine = _make_engine(FALLBACK_DATABASE_URL)
    async_session_factory.configure(bind=engine)
    _database_url = FALLBACK_DATABASE_URL

    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    logger.warning(
        "Falling back to SQLite because the configured database is unavailable: %s",
        FALLBACK_DATABASE_PATH,
    )


async def init_database() -> None:
    try:
        async with engine.begin() as connection:
            await connection.execute(text("SELECT 1"))
            if _database_url.startswith("sqlite"):
                await connection.run_sync(Base.metadata.create_all)
    except Exception:
        if _should_fallback_to_sqlite(_database_url):
            await _enable_sqlite_fallback()
            return
        raise


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
