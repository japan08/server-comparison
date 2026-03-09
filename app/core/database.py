from collections.abc import AsyncGenerator
from typing import Annotated

from fastapi import Depends
from sqlalchemy import text
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_settings
from app.models import Base

settings = get_settings()
active_database_url = settings.database_url
database_ready = False


def _build_engine(url: str):
    return create_async_engine(
        url,
        echo=False,
        future=True,
    )


engine = _build_engine(active_database_url)

async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


def _is_sqlite(url: str) -> bool:
    return url.startswith("sqlite+aiosqlite://")


def _reconfigure_database(url: str) -> None:
    global active_database_url, engine, async_session_factory
    active_database_url = url
    engine = _build_engine(url)
    async_session_factory = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False,
    )


async def _create_tables() -> None:
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)


async def ensure_database_ready() -> None:
    global database_ready

    if database_ready:
        return

    try:
        async with engine.connect() as connection:
            await connection.execute(text("SELECT 1"))
    except (OSError, OperationalError) as exc:
        if active_database_url == settings.fallback_database_url:
            raise

        await engine.dispose()
        _reconfigure_database(settings.fallback_database_url)
        print(
            "Primary database is unreachable; using local SQLite fallback "
            f"at {settings.fallback_database_url}."
        )
        await _create_tables()
        database_ready = True
        return

    if _is_sqlite(active_database_url):
        await _create_tables()

    database_ready = True


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    await ensure_database_ready()
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
