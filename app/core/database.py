from collections.abc import AsyncGenerator
import logging
from typing import Annotated

from fastapi import Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_settings
from app.models import Base

logger = logging.getLogger(__name__)
settings = get_settings()


def _build_engine(url: str):
    return create_async_engine(
        url,
        echo=False,
        future=True,
        pool_pre_ping=True,
    )


active_database_url = settings.database_url
engine = _build_engine(active_database_url)

async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


async def _can_connect() -> bool:
    try:
        async with engine.connect() as connection:
            await connection.execute(text("SELECT 1"))
        return True
    except Exception as exc:
        logger.warning(
            "Database connection failed for the configured database (%s).",
            exc.__class__.__name__,
        )
        return False


async def _ensure_schema() -> None:
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)


async def initialize_database() -> None:
    global active_database_url, engine

    if not await _can_connect():
        fallback_url = settings.sqlite_database_url
        if active_database_url != fallback_url:
            await engine.dispose()
            active_database_url = fallback_url
            engine = _build_engine(active_database_url)
            async_session_factory.configure(bind=engine)
            logger.warning(
                "Falling back to local SQLite database at %s.",
                active_database_url,
            )

    await _ensure_schema()


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
