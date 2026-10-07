"""
HYQUB — Transaction Intent API

Provides the canonical TransactionIntent hash that a client must sign
with its ML-DSA private key before submitting a transaction.

Flow:

Client
  |
  | wallet_address
  | target
  | value_wei
  | data
  v
GET /transaction-intent
  |
  | HYQUB gets:
  | - real chain ID
  | - registered wallet key version
  | - canonical ABI encoding
  |
  v
message_hash
  |
  v
Client signs with ML-DSA
  |
  v
POST /submit-transaction
"""

from fastapi import APIRouter, HTTPException, Query
from web3 import Web3

from app.crypto.transaction_intent import hash_transaction_intent
from app.models.transaction_intent import (
    TransactionIntentRequest,
    TransactionIntentResponse,
)
from app.utils.blockchain import get_web3, get_key_version


router = APIRouter(
    tags=["Transaction Intent"],
)


@router.get(
    "/transaction-intent",
    response_model=TransactionIntentResponse,
)
def get_transaction_intent(
    wallet_address: str = Query(...),
    target: str = Query(...),
    value_wei: int = Query(..., ge=0),
    data: str = Query(default="0x"),
) -> TransactionIntentResponse:
    """
    Return the exact canonical TransactionIntent hash that the client
    must sign using its ML-DSA private key.

    The backend is the single source of truth for:
    - chain ID
    - key version
    - transaction intent encoding
    - SHA-256 hash
    """

    try:
        request = TransactionIntentRequest(
            wallet_address=wallet_address,
            target=target,
            value_wei=value_wei,
            data=data,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=422,
            detail=str(exc),
        ) from exc

    try:
        web3 = get_web3()

        checksum_wallet = Web3.to_checksum_address(
            request.wallet_address
        )

        checksum_target = Web3.to_checksum_address(
            request.target
        )

        chain_id = web3.eth.chain_id

        key_version = get_key_version(
            checksum_wallet
        )

        data_bytes = bytes.fromhex(
            request.data[2:]
        )

        message_hash = hash_transaction_intent(
            chain_id=chain_id,
            wallet_address=checksum_wallet,
            target=checksum_target,
            value=request.value_wei,
            data=data_bytes,
            key_version=key_version,
        )

        return TransactionIntentResponse(
            wallet_address=checksum_wallet,
            target=checksum_target,
            value_wei=request.value_wei,
            data=request.data,
            chain_id=chain_id,
            key_version=key_version,
            message_hash=message_hash,
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to prepare transaction intent: {exc}",
        ) from exc
