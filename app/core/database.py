from collections.abc import AsyncGenerator
from typing import Annotated

from fastapi import Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import DEFAULT_DATABASE_URL, get_settings
from app.models import Base


def _build_engine(url: str):
    return create_async_engine(url, echo=False, future=True)


def _build_session_factory(engine):
    return async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False,
    )


engine = _build_engine(get_settings().database_url)
async_session_factory = _build_session_factory(engine)


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


async def initialize_database() -> None:
    global engine, async_session_factory

    try:
        async with engine.begin() as connection:
            if engine.url.get_backend_name() == "sqlite":
                await connection.run_sync(Base.metadata.create_all)
            else:
                await connection.execute(text("SELECT 1"))
        return
    except Exception:
        if engine.url.get_backend_name() == "sqlite":
            raise

    await engine.dispose()
    engine = _build_engine(DEFAULT_DATABASE_URL)
    async_session_factory = _build_session_factory(engine)

    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)


DbSession = Annotated[AsyncSession, Depends(get_db)]
