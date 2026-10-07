"""
HYQUB — Submit Transaction Models
===================================

Defines the request/response contracts for POST /submit-transaction.

Design note: the client supplies the raw transaction fields (target,
value, data) and an ML-DSA signature over the resulting TransactionIntent
hash. The backend ALWAYS recomputes message_hash itself from those raw
fields plus the wallet's registered key_version and the chain's real
chain_id — it never trusts a client-supplied hash. This means the
client must already know how to construct a matching TransactionIntent
hash before signing (chain_id + current key_version); a future
GET /transaction-intent endpoint would let a client fetch those values
and the exact hash to sign, rather than reimplementing the encoding
independently. That endpoint doesn't exist yet — this is a known,
acceptable v1 gap.

    Client
       │
       ▼
    SubmitTransactionRequest (Pydantic)
       │
       ▼
    FastAPI validates it
       │
       ▼
    submit_transaction_service.py:
        - recompute message_hash from raw fields
        - verify ML-DSA signature via quorum
        - create signed ApprovalToken
        - build + submit PackedUserOperation to EntryPoint
       │
       ▼
    SubmitTransactionResponse
"""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator

from app.models.register import WALLET_ADDRESS_REGEX


class SubmitTransactionRequest(BaseModel):
    """
    Incoming payload for POST /submit-transaction.

    The client claims to control `wallet_address` and proves it by
    supplying `ml_dsa_signature`, produced with the ML-DSA private key
    corresponding to the public key stored during registration, over
    the TransactionIntent hash that (target, value, data, wallet's
    current key_version, chain_id) canonically produce.
    """

    wallet_address: str = Field(
        ...,
        description="ERC-4337 Smart Account address (0x-prefixed, 40 hex chars).",
        examples=["0x9fe46736679d2d9a65f0992f2272de9f3c7fa6e0"],
    )
    target: str = Field(
        ...,
        description="Address the wallet will call or send value to.",
        examples=["0x4444444444444444444444444444444444444444"],
    )
    value_wei: int = Field(
        ...,
        ge=0,
        description="Amount of wei to send with the call.",
    )
    data: str = Field(
        default="0x",
        description="Hex-encoded calldata for the call. '0x' for a plain value transfer.",
    )
    ml_dsa_signature: str = Field(
        ...,
        min_length=1,
        description="ML-DSA (Dilithium) signature over the TransactionIntent hash, base64 encoded.",
    )

    @field_validator("wallet_address", "target")
    @classmethod
    def validate_address(cls, v: str) -> str:
        import re

        if not re.match(WALLET_ADDRESS_REGEX, v):
            raise ValueError(
                "must be a valid 0x-prefixed 20-byte Ethereum address"
            )
        return v.lower()

    @field_validator("data")
    @classmethod
    def validate_data_hex(cls, v: str) -> str:
        if not v.startswith("0x"):
            raise ValueError("data must be 0x-prefixed hex")
        try:
            bytes.fromhex(v[2:])
        except ValueError as exc:
            raise ValueError("data must be valid hex") from exc
        return v


class SubmitTransactionResponse(BaseModel):
    """Response returned to the client after a transaction submission attempt."""

    success: bool = Field(
        ..., description="True if the UserOperation was accepted and executed on-chain."
    )
    message: str = Field(
        ..., description="Human-readable result, e.g. success or failure reason."
    )
    transaction_hash: str | None = Field(
        default=None,
        description="Blockchain transaction hash for the handleOps call, if submitted.",
    )
    approval_nonce: int | None = Field(
        default=None,
        description="The nonce assigned to this approval, for client-side tracking.",
    )
