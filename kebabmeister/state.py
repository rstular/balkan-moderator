from asyncio import AbstractEventLoop

from asyncpraw import Reddit
from asyncpraw.models.reddit.redditor import Redditor
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from kebabmeister.configuration import Configuration

loop: AbstractEventLoop

db_engine: AsyncEngine
db_session: async_sessionmaker[AsyncSession]

config: Configuration
reddit: Reddit

me: Redditor
