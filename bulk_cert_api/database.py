"""
Database engine and session factory.

Uses SQLAlchemy 2.x async engine backed by aiosqlite (SQLite) for
development.  To switch to PostgreSQL, change DATABASE_URL in .env to a
postgresql+asyncpg://... connection string and add asyncpg to requirements.
"""

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from bulk_cert_api.config import settings

engine = create_async_engine(
    settings.database_url,
    # SQLite-specific: allow the connection to be used across threads
    connect_args={"check_same_thread": False} if "sqlite" in settings.database_url else {},
    echo=settings.app_env == "development",
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    """Declarative base shared by all ORM models."""
    pass


async def get_db() -> AsyncSession:  # type: ignore[return]
    """FastAPI dependency that provides a database session per request."""
    async with AsyncSessionLocal() as session:
        yield session
