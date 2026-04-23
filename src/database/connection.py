from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.pool import NullPool
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Optional
from src.utils.logger import get_logger
from config.settings import settings

logger = get_logger(__name__)

# Global engine - may be None if DB unavailable
engine = None
AsyncSessionLocal = None
_db_available = False


def _init_engine():
    """Initialize database engine with error handling."""
    global engine, AsyncSessionLocal, _db_available
    try:
        engine = create_async_engine(
            settings.database_url,
            pool_size=5,
            max_overflow=10,
            pool_pre_ping=True,
            pool_timeout=10,
            connect_args={"timeout": 10},
            echo=False,
        )
        AsyncSessionLocal = async_sessionmaker(
            engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )
        _db_available = True
        logger.info("Database engine initialized")
    except Exception as e:
        logger.warning(f"Database engine init failed: {e} — running without DB")
        _db_available = False


# Try to initialize on import
try:
    _init_engine()
except Exception as e:
    logger.warning(f"Database unavailable: {e}")


@asynccontextmanager
async def get_session() -> AsyncGenerator[Optional[AsyncSession], None]:
    """Provide a transactional database session. Yields None if DB unavailable."""
    if not _db_available or AsyncSessionLocal is None:
        yield None
        return

    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def create_tables():
    """Create all tables defined in models. Safe to call even if DB unavailable."""
    global _db_available
    if not _db_available or engine is None:
        logger.warning("Skipping table creation — database not available")
        return

    try:
        from src.database.models import Base
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("Database tables created successfully")
        _db_available = True
    except Exception as e:
        logger.warning(f"Table creation failed: {e} — continuing without DB")
        _db_available = False


async def check_db_connection() -> bool:
    """Check if database is reachable."""
    global _db_available
    if engine is None:
        return False
    try:
        async with engine.connect() as conn:
            await conn.execute(__import__('sqlalchemy').text("SELECT 1"))
        _db_available = True
        return True
    except Exception as e:
        logger.warning(f"DB connection check failed: {e}")
        _db_available = False
        return False


async def drop_tables():
    """Drop all tables (use only in tests)."""
    if not _db_available or engine is None:
        return
    from src.database.models import Base
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


async def close_db():
    """Close all database connections."""
    if engine:
        await engine.dispose()
        logger.info("Database connections closed")


def is_db_available() -> bool:
    """Check if database is available."""
    return _db_available
