"""
pytest configuration and shared fixtures.

Provides:
- An isolated SQLite test database per test
- Temporary certificate directory for test runs
- AsyncClient fixture for FastAPI endpoint tests
"""

import pathlib
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from bulk_cert_api.config import settings
from bulk_cert_api.database import Base, get_db
from bulk_cert_api.main import app


@pytest.fixture(scope="session")
def anyio_backend():
    return "asyncio"


@pytest.fixture
async def test_env(tmp_path, monkeypatch):
    """Sets up a temporary certificate directory and isolated test database."""
    test_certs_dir = tmp_path / "test_certificates"
    test_certs_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(settings, "certificates_dir", str(test_certs_dir))

    db_path = tmp_path / "test_api.db"
    test_db_url = f"sqlite+aiosqlite:///{db_path}"
    test_engine = create_async_engine(
        test_db_url,
        connect_args={"check_same_thread": False},
    )

    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    test_session_maker = async_sessionmaker(
        bind=test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    async def _override_get_db():
        async with test_session_maker() as session:
            yield session

    app.dependency_overrides[get_db] = _override_get_db

    yield {
        "certs_dir": test_certs_dir,
        "db_url": test_db_url,
        "session_maker": test_session_maker,
    }

    app.dependency_overrides.pop(get_db, None)
    await test_engine.dispose()


@pytest.fixture
async def client(test_env):
    """Async HTTP test client for the FastAPI app with isolated DB and storage."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac
