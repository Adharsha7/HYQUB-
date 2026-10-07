"""
HYQUB — Register API
======================

Sole responsibility: expose POST /register over HTTP.

    Receive HTTP Request
        ↓
    Pydantic Validation      (FastAPI does this automatically via RegisterRequest)
        ↓
    Register Service
        ↓
    Return Response

This file does NOT:
    - hash anything
    - touch storage directly
    - build a SecurityProfile

All of that already exists in register_service.py / utils/storage.py.
This route is intentionally thin.
"""

from fastapi import APIRouter, HTTPException, status

from app.models.register import RegisterRequest, RegisterResponse
from app.services.register_service import (
    WalletAlreadyRegisteredError,
    register_wallet,
)
from app.utils.storage import storage

router = APIRouter()


@router.post(
    "/register",
    response_model=RegisterResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a wallet's ML-DSA public key",
)
def register(request: RegisterRequest) -> RegisterResponse:
    """
    Register a new wallet by storing its ML-DSA public key as a
    Security Profile.

    Returns:
        201 Created with RegisterResponse on success.

    Raises:
        409 Conflict if the wallet is already registered.
    """
    try:
        return register_wallet(request, storage)
    except WalletAlreadyRegisteredError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
