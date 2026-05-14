"""Health check endpoint — used by Docker and load balancers."""
from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    status: str
    services: dict


@router.get("/health", response_model=HealthResponse)
async def health():
    """
    Liveness + readiness probe.
    TODO: add actual connectivity checks for Qdrant, Postgres, Redis.
    """
    return HealthResponse(
        status="ok",
        services={
            "qdrant":   "TODO: check",
            "postgres": "TODO: check",
            "redis":    "TODO: check",
        },
    )
