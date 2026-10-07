"""
HYQUB — Verify Models
=======================

Defines the request/response contracts for POST /verify.

Design note: verification proves that whoever holds the ML-DSA private
key for a wallet's registered public key actually signed `message`.
This module only defines the shapes going in and out over HTTP — the
actual ML-DSA signature check happens later in verify_service.py, once
ML-DSA integration lands. This file does no cryptography.

    Client
       │
       ▼
    VerifyRequest (Pydantic)
       │
       ▼
    FastAPI validates it
       │
       ▼
    verify_service.py checks the signature
       │
       ▼
    VerifyResponse
"""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator

# Reuse the exact same wallet address pattern used during registration,
# so a wallet that was accepted by /register is guaranteed to also be
# accepted (format-wise) by /verify. Importing rather than redefining
# keeps this a single source of truth.
from app.models.register import WALLET_ADDRESS_REGEX


# ---------------------------------------------------------------------------
# Request
# ---------------------------------------------------------------------------

class VerifyRequest(BaseModel):
    """
    Incoming payload for POST /verify.

    The client claims to control `wallet_address` and proves it by
    supplying a `signature` over `message`, produced with the ML-DSA
    private key corresponding to the public key stored during
    registration.
    """

    wallet_address: str = Field(
        ...,
        description="ERC-4337 Smart Account address (0x-prefixed, 40 hex chars).",
        examples=["0x1234567890abcdef1234567890abcdef12345678"],
    )
    message: str = Field(
        ...,
        min_length=1,
        description="The original message that was signed.",
    )
    signature: str = Field(
        ...,
        min_length=1,
        description="ML-DSA (Dilithium) signature over `message`, base64 or hex encoded.",
    )

    @field_validator("wallet_address")
    @classmethod
    def validate_wallet_address(cls, v: str) -> str:
        import re

        if not re.match(WALLET_ADDRESS_REGEX, v):
            raise ValueError(
                "wallet_address must be a valid 0x-prefixed 20-byte Ethereum address"
            )
        # Normalize to lowercase, same as RegisterRequest, so lookups
        # against storage (keyed by the lowercased address) always match.
        return v.lower()

    @field_validator("message")
    @classmethod
    def validate_message_not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("message must not be blank")
        return v

    @field_validator("signature")
    @classmethod
    def validate_signature_not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("signature must not be blank")
        return v.strip()


# ---------------------------------------------------------------------------
# Response
# ---------------------------------------------------------------------------

class VerifyResponse(BaseModel):
    """Response returned to the client after a verification attempt."""

    verified: bool = Field(
        ..., description="True if the signature is valid for the registered public key."
    )
    message: str = Field(
        ..., description="Human-readable result, e.g. success or failure reason."
    )
