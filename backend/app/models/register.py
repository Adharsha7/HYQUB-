"""
HYQUB — Registration Models
============================

Defines the request/response contracts for POST /register.

Design decision (see conversation): identity is the wallet_address
(ERC-4337 Smart Account), not a username or email. Everything else —
ML-DSA public key, key version, registration time, status — hangs off
that wallet as a "Security Profile".

    Wallet Address
        │
        ▼
    Security Profile
        ├── ml_dsa_public_key_hash
        ├── key_version
        ├── registered_at
        ├── status
        └── metadata
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, field_validator


# ---------------------------------------------------------------------------
# Shared validation helpers
# ---------------------------------------------------------------------------

WALLET_ADDRESS_REGEX = r"^0x[a-fA-F0-9]{40}$"


class SecurityProfileStatus(str, Enum):
    """Lifecycle state of a wallet's security profile."""

    ACTIVE = "active"
    PENDING = "pending"
    REVOKED = "revoked"
    ROTATED = "rotated"  # key was rotated, profile superseded


# ---------------------------------------------------------------------------
# Request
# ---------------------------------------------------------------------------

class RegisterRequest(BaseModel):
    """
    Incoming payload for POST /register.

    The client (the ERC-4337 Smart Account / its owner) proves nothing
    cryptographically at this stage — that's what /verify is for later.
    This step only registers the wallet's post-quantum public key.
    """

    wallet_address: str = Field(
        ...,
        description="ERC-4337 Smart Account address (0x-prefixed, 40 hex chars).",
        examples=["0x1234567890abcdef1234567890abcdef12345678"],
    )
    ml_dsa_public_key: str = Field(
        ...,
        min_length=1,
        description="ML-DSA (Dilithium) public key, base64 or hex encoded.",
    )

    @field_validator("wallet_address")
    @classmethod
    def validate_wallet_address(cls, v: str) -> str:
        import re

        if not re.match(WALLET_ADDRESS_REGEX, v):
            raise ValueError(
                "wallet_address must be a valid 0x-prefixed 20-byte Ethereum address"
            )
        # Normalize to lowercase for consistent storage/lookup.
        # (Checksum validation can be layered in later via eth-utils.)
        return v.lower()

    @field_validator("ml_dsa_public_key")
    @classmethod
    def validate_public_key_not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("ml_dsa_public_key must not be blank")
        return v.strip()


# ---------------------------------------------------------------------------
# Response
# ---------------------------------------------------------------------------
class RegisterResponse(BaseModel):
    """Response returned to the client after successful registration."""

    success: bool = True
    message: str = "Registration successful"
    key_version: int = Field(
        ..., description="Version number of the registered ML-DSA key (starts at 1)."
    )
    transaction_hash: str | None = Field(
        default=None,
        description=(
            "Blockchain transaction hash for the wallet registration, "
            "or None if the wallet was already registered on-chain and "
            "this call only synced local storage."
        ),
    )


# ---------------------------------------------------------------------------
# Internal domain model — the Security Profile
# ---------------------------------------------------------------------------

class SecurityProfile(BaseModel):
    """
    The full record the backend stores per wallet.

    Only a hash of the public key is treated as the "identity fingerprint"
    for quick comparisons/indexing; the raw public key is also retained
    because ML-DSA verification needs the actual key material, not just
    its hash. (On-chain, only the hash — or a commitment to it — would
    ever be published.)
    """

    wallet_address: str
    ml_dsa_public_key: str
    ml_dsa_public_key_hash: str = Field(
        ..., description="SHA-256 (or similar) hash of the public key, hex-encoded."
    )
    key_version: int = Field(default=1, ge=1)
    registered_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    status: SecurityProfileStatus = SecurityProfileStatus.ACTIVE
    metadata: Optional[dict] = Field(
        default=None,
        description="Optional non-identity metadata (e.g. display name, client version).",
    )

    class Config:
        use_enum_values = True
