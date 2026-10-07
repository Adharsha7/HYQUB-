"""
HYQUB — Key Rotation Models
==============================

Defines the request/response contracts for POST /rotate.

Design note: rotation lets a wallet replace its registered ML-DSA
public key WITHOUT changing its wallet address or losing its identity.
This matters if a user suspects their private key was compromised —
they rotate to a new keypair rather than abandoning the wallet
entirely.

    Old Key
        │
        ▼
    Rotate Key
        │
        ▼
    New Public Key Registered
        │
        ▼
    key_version += 1

This module only defines the shapes going in and out over HTTP — the
actual rotation logic (fetching the existing profile, bumping
key_version, replacing the key, persisting it) happens in
rotate_service.py. This file does no storage access and no crypto.
"""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator

# Reuse the exact same wallet address pattern used during registration
# and verification, so a wallet accepted by /register is guaranteed to
# also be accepted (format-wise) by /rotate. Single source of truth.
from app.models.register import WALLET_ADDRESS_REGEX


# ---------------------------------------------------------------------------
# Request
# ---------------------------------------------------------------------------

class RotateKeyRequest(BaseModel):
    """
    Incoming payload for POST /rotate.

    The client identifies the wallet whose key is being rotated and
    supplies the new ML-DSA public key that should replace the
    currently registered one.
    """

    wallet_address: str = Field(
        ...,
        description="ERC-4337 Smart Account address (0x-prefixed, 40 hex chars).",
        examples=["0x1234567890abcdef1234567890abcdef12345678"],
    )
    new_ml_dsa_public_key: str = Field(
        ...,
        min_length=1,
        description="New ML-DSA (Dilithium) public key that replaces the current one.",
    )

    @field_validator("wallet_address")
    @classmethod
    def validate_wallet_address(cls, v: str) -> str:
        import re

        if not re.match(WALLET_ADDRESS_REGEX, v):
            raise ValueError(
                "wallet_address must be a valid 0x-prefixed 20-byte Ethereum address"
            )
        # Normalize to lowercase, same as RegisterRequest/VerifyRequest,
        # so lookups against storage (keyed by the lowercased address)
        # always match.
        return v.lower()

    @field_validator("new_ml_dsa_public_key")
    @classmethod
    def validate_public_key_not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("new_ml_dsa_public_key must not be blank")
        return v.strip()


# ---------------------------------------------------------------------------
# Response
# ---------------------------------------------------------------------------

class RotateKeyResponse(BaseModel):
    """Response returned to the client after a successful key rotation."""

    success: bool = True
    message: str = "Key rotation successful"
    key_version: int = Field(
        ..., description="New key version after rotation (previous version + 1)."
    )
