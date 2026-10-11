"""
FastAPI application entry point.

Responsibilities
----------------
- Create the FastAPI app instance with metadata.
- Register all routers.
- Configure lifespan events (startup / shutdown):
    - Ensure the certificates output directory exists.
    - Create database tables (dev convenience; production uses Alembic).
- Configure structured logging.

Run locally
-----------
    uvicorn bulk_cert_api.main:app --reload
"""

import logging
import pathlib
from contextlib import asynccontextmanager

from fastapi import FastAPI

from bulk_cert_api.config import settings
from bulk_cert_api.database import Base, engine
from bulk_cert_api.routers.health import router as health_router

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=settings.log_level.upper(),
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Lifespan — startup & shutdown
# ---------------------------------------------------------------------------


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: runs startup logic, yields, then shutdown."""

    # --- Startup ---
    logger.info("Starting Bulk Certificate Generator API (env=%s)", settings.app_env)

    # Ensure certificate output directory exists
    cert_dir = pathlib.Path(settings.certificates_dir)
    cert_dir.mkdir(parents=True, exist_ok=True)
    logger.info("Certificate output directory: %s", cert_dir.resolve())

    # Create DB tables (idempotent; in production, use Alembic migrations)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database tables verified/created.")

    yield  # Application runs here

    # --- Shutdown ---
    await engine.dispose()
    logger.info("Database engine disposed. Shutdown complete.")


# ---------------------------------------------------------------------------
# App factory
# ---------------------------------------------------------------------------


def create_app() -> FastAPI:
    app = FastAPI(
        title="Bulk Certificate Generator API",
        description=(
            "Submit bulk certificate generation jobs, track their progress, "
            "and download the generated PDF certificates."
        ),
        version="1.0.0",
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
    )

    # Routers
    app.include_router(health_router)
    # Future routers (added in later modules):
    # app.include_router(jobs_router, prefix="/jobs")
    # app.include_router(certificates_router, prefix="/certificates")

    return app


app = create_app()


# ---------------------------------------------------------------------------
# Dev entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "bulk_cert_api.main:app",
        host=settings.app_host,
        port=settings.app_port,
        reload=settings.app_env == "development",
        log_level=settings.log_level,
    )
