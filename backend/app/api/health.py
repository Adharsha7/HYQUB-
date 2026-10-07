"""
System-level endpoints: root welcome message and /health.

Kept in their own router (rather than in main.py) so that /register,
/verify, and /rotate can each get their own router file in Sprint 3
without ever needing to touch this file or main.py again.
"""
from fastapi import APIRouter

from app.config import get_settings
from app.models.common import HealthResponse, RootResponse

router = APIRouter(tags=["system"])


@router.get("/", response_model=RootResponse)
def root() -> RootResponse:
    settings = get_settings()
    return RootResponse(
        message=f"Welcome to {settings.app_name}",
        docs_url="/docs",
    )


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    """
    Liveness check. Each verifier instance (A, B, ...) exposes its own
    /health — this is what the Quorum Manager can poll to decide whether
    a verifier is reachable before counting on its vote.
    """
    settings = get_settings()
    return HealthResponse(
        status="healthy",
        service=settings.app_name,
        version=settings.version,
        environment=settings.environment,
        verifier_id=settings.verifier_id,
    )
