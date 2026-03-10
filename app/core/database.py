from collections.abc import AsyncGenerator
from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_settings
from app.models import Base

database_url = get_settings().database_url
using_sqlite = database_url.startswith("sqlite+")

engine = create_async_engine(
    database_url,
    echo=False,
    future=True,
)

async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


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


async def init_db() -> None:
    """Create tables for zero-config local SQLite runs."""
    if not using_sqlite:
        return

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


DbSession = Annotated[AsyncSession, Depends(get_db)]
