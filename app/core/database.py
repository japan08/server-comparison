import logging
from collections.abc import AsyncGenerator
from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_settings
from app.models import Base

logger = logging.getLogger(__name__)


def _create_engine(database_url: str) -> AsyncEngine:
    return create_async_engine(
        database_url,
        echo=False,
        future=True,
    )


settings = get_settings()
engine = _create_engine(settings.database_url)

async_session_factory = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)

_database_initialized = False


async def _prepare_database(target_engine: AsyncEngine) -> None:
    async with target_engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)


async def initialize_database() -> None:
    global _database_initialized
    global engine

    if _database_initialized:
        return

    try:
        await _prepare_database(engine)
    except Exception:
        if not settings.database_url_allows_fallback:
            raise

        fallback_engine = _create_engine(settings.sqlite_fallback_url)
        await _prepare_database(fallback_engine)
        await engine.dispose()
        engine = fallback_engine
        async_session_factory.configure(bind=engine)
        logger.warning(
            "Configured database was unavailable; using SQLite fallback at %s",
            settings.sqlite_fallback_url,
        )

    _database_initialized = True


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
