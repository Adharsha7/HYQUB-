"""
HYQUB — Approval Token Model

Represents the authorization produced after the required
post-quantum verifier quorum has been satisfied.

The token is intentionally represented as structured data first.
Cryptographic signing and replay protection are added in the
next steps.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class ApprovalTokenPayload(BaseModel):
    """
    Data that will eventually be signed by the HYQUB approval key.
    """

    wallet_address: str = Field(
        ...,
        min_length=42,
        max_length=42,
        description="Ethereum wallet address receiving the approval.",
    )

    message_hash: str = Field(
        ...,
        min_length=64,
        max_length=64,
        description="SHA-256 hash of the authorized message.",
    )

    key_version: int = Field(
        ...,
        ge=1,
        description="ML-DSA key version approved by the quorum.",
    )

    nonce: int = Field(
        ...,
        ge=0,
        description="Unique nonce preventing approval replay.",
    )

    issued_at: int = Field(
        ...,
        ge=0,
        description="Unix timestamp when the approval was issued.",
    )

    expires_at: int = Field(
        ...,
        ge=0,
        description="Unix timestamp after which the approval expires.",
    )

    verifier_ids: list[str] = Field(
        ...,
        min_length=1,
        description="Verifier instances that approved the request.",
    )


class ApprovalToken(BaseModel):
    """
    Signed HYQUB approval token.

    The signature will be generated after the payload has
    successfully passed the required verifier quorum.
    """

    payload: ApprovalTokenPayload

    signature: str = Field(
        ...,
        min_length=1,
        description="ECDSA signature over the approval payload.",
    )
