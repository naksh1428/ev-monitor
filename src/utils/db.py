from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import sessionmaker

from utils.config import settings

# Async engine/session for FastAPI route dependencies.
async_engine = create_async_engine(settings.DATABASE_URL.replace("mysql+pymysql", "mysql+aiomysql"))
AsyncLocalSession = async_sessionmaker(bind=async_engine, expire_on_commit=False)


async def get_db():
    async with AsyncLocalSession() as session:
        yield session


# Sync engine/session for the Celery worker task: Celery's default (prefork) pool
# runs task functions synchronously, so it cannot use an asyncio session.
sync_engine = create_engine(settings.DATABASE_URL)
LocalSession = sessionmaker(bind=sync_engine)
