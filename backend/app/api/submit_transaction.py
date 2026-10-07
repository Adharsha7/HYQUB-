"""
HYQUB — Submit Transaction API
================================

Sole responsibility: expose POST /submit-transaction over HTTP.

    Receive HTTP Request
        ↓
    Pydantic Validation      (FastAPI does this automatically via SubmitTransactionRequest)
        ↓
    Submit Transaction Service
        ↓
    Return Response

This file does NOT:
    - verify any signature itself
    - build TransactionIntent or ApprovalToken payloads
    - talk to web3 directly

All of that lives in submit_transaction_service.py / utils/blockchain.py.
This route is intentionally thin — same pattern as api/register.py and
api/verify.py.
"""

from fastapi import APIRouter, HTTPException, status

from app.models.submit_transaction import (
    SubmitTransactionRequest,
    SubmitTransactionResponse,
)
from app.services.submit_transaction_service import (
    TransactionNotApprovedError,
    TransactionSubmissionError,
    submit_transaction,
)
from app.services.verify_service import WalletNotRegisteredError
from app.utils.storage import storage

router = APIRouter()


@router.post(
    "/submit-transaction",
    response_model=SubmitTransactionResponse,
    status_code=status.HTTP_200_OK,
    summary="Verify an ML-DSA-signed transaction and submit it as a UserOperation",
)
def submit(request: SubmitTransactionRequest) -> SubmitTransactionResponse:
    """
    Verify a wallet's ML-DSA signature over a transaction intent through
    the HYQUB verifier quorum, then submit it as a real ERC-4337
    UserOperation via the EntryPoint.

    Returns:
        200 OK with SubmitTransactionResponse on successful execution.

    Raises:
        404 Not Found if the wallet has no registered Security Profile.
        400 Bad Request if the verifier quorum does not approve the
            transaction (e.g. invalid or insufficient signatures).
        502 Bad Gateway if approval creation or the on-chain submission
            itself fails (e.g. reverted transaction, RPC error).
    """
    try:
        return submit_transaction(request, storage)
    except WalletNotRegisteredError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except TransactionNotApprovedError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except TransactionSubmissionError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc
