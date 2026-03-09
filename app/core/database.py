import logging
from collections.abc import AsyncGenerator
from pathlib import Path
from typing import Annotated

from fastapi import Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_settings
from app.models import Base

logger = logging.getLogger(__name__)
settings = get_settings()
FALLBACK_DATABASE_PATH = Path(__file__).resolve().parents[2] / "cloud_compare.db"
FALLBACK_DATABASE_URL = f"sqlite+aiosqlite:///{FALLBACK_DATABASE_PATH}"


def _build_engine(database_url: str):
    connect_args = (
        {"check_same_thread": False}
        if database_url.startswith("sqlite+aiosqlite://")
        else {}
    )
    return create_async_engine(
        database_url,
        echo=False,
        future=True,
        connect_args=connect_args,
    )


engine = _build_engine(settings.database_url)

async_session_factory = async_sessionmaker(
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)
async_session_factory.configure(bind=engine)


async def initialize_database() -> None:
    global engine
    try:
        async with engine.begin() as connection:
            await connection.execute(text("SELECT 1"))
    except Exception:
        if settings.database_url.startswith("sqlite+aiosqlite://"):
            raise

        logger.warning(
            "Configured database is unavailable; falling back to local SQLite at %s",
            FALLBACK_DATABASE_PATH,
        )
        engine = _build_engine(FALLBACK_DATABASE_URL)
        async_session_factory.configure(bind=engine)

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
