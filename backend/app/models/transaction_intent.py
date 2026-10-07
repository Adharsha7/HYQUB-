"""
HYQUB — Transaction Intent Models

Defines the request and response models for GET /transaction-intent.

This endpoint gives clients the canonical TransactionIntent hash that
must be signed using the wallet's ML-DSA private key before calling
POST /submit-transaction.

The client does not need to know:
- ABI encoding rules
- Field ordering
- SHA-256 implementation
- Current chain ID
- Current wallet key version

HYQUB computes all of those values server-side.
"""

from __future__ import annotations

import re

from pydantic import BaseModel, Field, field_validator

from app.models.register import WALLET_ADDRESS_REGEX


class TransactionIntentRequest(BaseModel):
    """
    Parameters required to construct a canonical TransactionIntent.
    """

    wallet_address: str = Field(
        ...,
        description="ERC-4337 HYQUB wallet address.",
        examples=["0x9fe46736679d2d9a65f0992f2272de9f3c7fa6e0"],
    )

    target: str = Field(
        ...,
        description="Address the HYQUB wallet will call.",
        examples=["0x4444444444444444444444444444444444444444"],
    )

    value_wei: int = Field(
        ...,
        ge=0,
        description="Amount of wei sent with the call.",
    )

    data: str = Field(
        default="0x",
        description="0x-prefixed calldata. Use 0x for plain ETH transfer.",
    )

    @field_validator("wallet_address", "target")
    @classmethod
    def validate_address(cls, value: str) -> str:
        if not re.match(WALLET_ADDRESS_REGEX, value):
            raise ValueError(
                "must be a valid 0x-prefixed 20-byte Ethereum address"
            )

        return value.lower()

    @field_validator("data")
    @classmethod
    def validate_data_hex(cls, value: str) -> str:
        if not value.startswith("0x"):
            raise ValueError("data must be 0x-prefixed hex")

        try:
            bytes.fromhex(value[2:])
        except ValueError as exc:
            raise ValueError(
                "data must be valid hex"
            ) from exc

        return value


class TransactionIntentResponse(BaseModel):
    """
    Canonical TransactionIntent information returned to the client.
    """

    wallet_address: str

    target: str

    value_wei: int

    data: str

    chain_id: int

    key_version: int

    message_hash: str
