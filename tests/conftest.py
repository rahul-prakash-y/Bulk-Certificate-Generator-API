"""
pytest configuration.

Provides:
- async_mode setting for pytest-asyncio
- A test FastAPI client that uses an in-memory SQLite database (populated in
  later modules when ORM models and routers are added)
"""

import pytest
from httpx import ASGITransport, AsyncClient

from bulk_cert_api.main import app


@pytest.fixture(scope="session")
def anyio_backend():
    return "asyncio"


@pytest.fixture
async def client():
    """Async HTTP test client for the FastAPI app."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac
