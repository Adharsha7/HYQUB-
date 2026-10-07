
"""
Shared response models. Typed Pydantic models (instead of raw dicts) give
you two things for free: automatic request/response validation, and
accurate schemas in the /docs Swagger UI — which matters when you're
demoing the API spec to your panel.
"""
from datetime import datetime, timezone

from pydantic import BaseModel, Field


class RootResponse(BaseModel):
    message: str
    docs_url: str


class HealthResponse(BaseModel):
    status: str
    service: str
    version: str
    environment: str
    verifier_id: str
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
