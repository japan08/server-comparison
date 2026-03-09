from collections.abc import AsyncGenerator
from typing import Annotated

from fastapi import Depends
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_settings
from app.models import Base

settings = get_settings()

engine = create_async_engine(
    settings.database_url,
    echo=False,
    future=True,
)
fallback_engine = create_async_engine(
    settings.fallback_database_url,
    echo=False,
    future=True,
)
active_engine = engine

async_session_factory = async_sessionmaker(
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


async def _initialize_engine(target_engine, *, create_schema: bool) -> None:
    async with target_engine.begin() as connection:
        await connection.execute(text("SELECT 1"))
        if create_schema:
            await connection.run_sync(Base.metadata.create_all)


async def init_db() -> None:
    global active_engine

    create_schema = engine.url.get_backend_name() == "sqlite"

    try:
        await _initialize_engine(engine, create_schema=create_schema)
        active_engine = engine
    except (OSError, SQLAlchemyError):
        # Fall back to a local SQLite database when the configured DB is unreachable.
        await _initialize_engine(fallback_engine, create_schema=True)
        active_engine = fallback_engine

    async_session_factory.configure(bind=active_engine)


async def close_db() -> None:
    await engine.dispose()
    if fallback_engine is not engine:
        await fallback_engine.dispose()


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
