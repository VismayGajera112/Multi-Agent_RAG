import time

from fastapi import APIRouter
from pydantic import BaseModel

from app.core.config import settings

router = APIRouter()


class HealthResponse(BaseModel):
    status: str
    service: str
    environment: str
    timestamp: float


class ReadinessResponse(BaseModel):
    status: str
    dependencies: dict


@router.get("/", response_model=HealthResponse)
async def health_check():
    """Liveness probe — process is up."""
    return HealthResponse(
        status="ok",
        service=settings.service_name,
        environment=settings.environment,
        timestamp=time.time(),
    )


@router.get("/ready", response_model=ReadinessResponse)
async def readiness_check():
    """Readiness probe — checks downstream dependencies (best-effort)."""
    deps: dict = {}

    try:
        from app.core.celery_app import check_broker

        deps["rabbitmq"] = "ok" if check_broker() else "unavailable"
    except Exception as exc:  # noqa: BLE001
        deps["rabbitmq"] = f"error: {exc}"

    try:
        from app.core.redis_client import get_client

        get_client().ping()
        deps["redis"] = "ok"
    except Exception as exc:  # noqa: BLE001
        deps["redis"] = f"error: {exc}"

    try:
        from app.core.qdrant_client import healthcheck

        deps["qdrant"] = "ok" if healthcheck() else "unavailable"
    except Exception as exc:  # noqa: BLE001
        deps["qdrant"] = f"error: {exc}"

    overall = "ok" if all(v == "ok" for v in deps.values()) else "degraded"
    return ReadinessResponse(status=overall, dependencies=deps)
