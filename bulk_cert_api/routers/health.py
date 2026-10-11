"""Health-check router."""

from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/health", summary="Health check")
async def health_check() -> dict[str, str]:
    """Returns 200 OK when the service is running."""
    return {"status": "ok"}
