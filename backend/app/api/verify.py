"""
HYQUB — Verify API
====================

Sole responsibility: expose POST /verify over HTTP.

    Receive HTTP Request
        ↓
    Pydantic Validation      (FastAPI does this automatically via VerifyRequest)
        ↓
    Verify Service
        ↓
    Return Response

This file does NOT:
    - check any signature itself
    - touch storage directly
    - know that the current signature check is a placeholder

All of that lives in verify_service.py / utils/storage.py. This route
is intentionally thin — same pattern as api/register.py.

⚠️ Reminder: verify_service.py's signature check is currently a
placeholder that always returns True (see its module docstring). This
endpoint will report `verified: true` for any registered wallet
regardless of whether the signature is genuine, until Step 8 (ML-DSA
Integration) replaces the placeholder.
"""

from fastapi import APIRouter, HTTPException, status

from app.models.verify import VerifyRequest, VerifyResponse
from app.services.verify_service import (
    WalletNotRegisteredError,
    verify_wallet_signature,
)
from app.utils.storage import storage

router = APIRouter()


@router.post(
    "/verify",
    response_model=VerifyResponse,
    status_code=status.HTTP_200_OK,
    summary="Verify a wallet's ML-DSA signature",
)
def verify(request: VerifyRequest) -> VerifyResponse:
    """
    Verify that a signature over a message was produced by the wallet's
    registered ML-DSA private key.

    Returns:
        200 OK with VerifyResponse (verified may be True or False).

    Raises:
        404 Not Found if the wallet has no registered Security Profile.
    """
    try:
        return verify_wallet_signature(request, storage)
    except WalletNotRegisteredError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
