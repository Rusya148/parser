import asyncio

from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine

from inviter.db.base import Base


def create_engine(database_url: str) -> AsyncEngine:
    return create_async_engine(database_url, echo=False, future=True)


def create_sessionmaker(engine: AsyncEngine) -> async_sessionmaker:
    return async_sessionmaker(bind=engine, expire_on_commit=False)


async def init_db(engine: AsyncEngine) -> None:
    attempts = 30
    delay = 1
    last_error: Exception | None = None
    for _ in range(attempts):
        try:
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            return
        except OperationalError as exc:
            last_error = exc
            await asyncio.sleep(delay)
    raise RuntimeError("Database is not ready after retries") from last_error
