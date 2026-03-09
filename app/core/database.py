from collections.abc import AsyncGenerator
import logging
from typing import Annotated

from fastapi import Depends
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_settings
from app.models import Base

logger = logging.getLogger(__name__)
settings = get_settings()


def _create_engine(database_url: str):
    return create_async_engine(
        database_url,
        echo=False,
        future=True,
    )


def _should_fallback_to_local_db(error: Exception) -> bool:
    db_url = make_url(settings.database_url)
    is_local_postgres = db_url.drivername.startswith("postgresql") and db_url.host in {
        None,
        "",
        "localhost",
        "127.0.0.1",
    }
    if not is_local_postgres:
        return False

    error_text = str(error).lower()
    return isinstance(error, OSError) or "connection refused" in error_text


engine = _create_engine(settings.database_url)

async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


async def _create_schema() -> None:
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)


async def initialize_database() -> None:
    global engine, async_session_factory

    try:
        await _create_schema()
    except Exception as error:
        if not _should_fallback_to_local_db(error):
            raise

        logger.warning(
            "Configured database is unavailable; falling back to local SQLite at %s",
            settings.local_database_url,
        )
        await engine.dispose()
        engine = _create_engine(settings.local_database_url)
        async_session_factory = async_sessionmaker(
            engine,
            class_=AsyncSession,
            expire_on_commit=False,
            autocommit=False,
            autoflush=False,
        )
        await _create_schema()


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
