from collections.abc import AsyncGenerator
from typing import Annotated

from fastapi import Depends
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_settings
from app.models import Base

settings = get_settings()


def _create_engine(database_url: str):
    return create_async_engine(
        database_url,
        echo=False,
        future=True,
    )


def _create_session_factory(db_engine):
    return async_sessionmaker(
        db_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False,
    )


def _should_fallback_to_sqlite(database_url: str, exc: Exception) -> bool:
    if not database_url.startswith(("postgresql://", "postgresql+asyncpg://")):
        return False

    host = make_url(database_url).host
    if host not in {"localhost", "127.0.0.1"}:
        return False

    error_text = str(exc).lower()
    return "connection refused" in error_text or "connect call failed" in error_text


engine = _create_engine(settings.database_url)
async_session_factory = _create_session_factory(engine)


async def initialize_database() -> None:
    global engine, async_session_factory

    try:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
    except Exception as exc:
        if not _should_fallback_to_sqlite(settings.database_url, exc):
            raise

        await engine.dispose()
        engine = _create_engine(settings.sqlite_fallback_url)
        async_session_factory = _create_session_factory(engine)

        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)


async def shutdown_database() -> None:
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
