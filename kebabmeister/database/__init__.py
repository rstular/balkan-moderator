from typing import Tuple

from loguru import logger
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from kebabmeister.configuration import DatabaseConfiguration
from kebabmeister.database.schemas import Base


@logger.catch
async def initialize_db(
    config: DatabaseConfiguration,
) -> Tuple[AsyncEngine, async_sessionmaker[AsyncSession]]:
    engine = create_async_engine(config.url)
    session = async_sessionmaker(engine, expire_on_commit=True)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    logger.debug("Database initialized")
    return engine, session
