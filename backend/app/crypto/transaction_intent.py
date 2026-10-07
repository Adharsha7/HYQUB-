"""
HYQUB — Transaction Intent Hashing

Creates the canonical message_hash for an authorized wallet action.

Python uses standard Ethereum ABI encoding so the resulting bytes
match Solidity's abi.encode(...) exactly.
"""

from __future__ import annotations

import hashlib

from eth_abi import encode


DOMAIN = "HYQUB_TX_V1"


def build_transaction_intent(
    *,
    chain_id: int,
    wallet_address: str,
    target: str,
    value: int,
    data: bytes,
    key_version: int,
) -> bytes:
    """
    Build the exact bytes produced by Solidity:

        abi.encode(
            "HYQUB_TX_V1",
            chainId,
            wallet,
            target,
            value,
            data,
            keyVersion
        )
    """

    if chain_id < 0:
        raise ValueError("chain_id cannot be negative")

    if value < 0:
        raise ValueError("value cannot be negative")

    if key_version < 1:
        raise ValueError("key_version must be >= 1")

    if not isinstance(data, bytes):
        raise ValueError("data must be bytes")

    return encode(
        [
            "string",
            "uint256",
            "address",
            "address",
            "uint256",
            "bytes",
            "uint256",
        ],
        [
            DOMAIN,
            chain_id,
            wallet_address,
            target,
            value,
            data,
            key_version,
        ],
    )


def hash_transaction_intent(
    *,
    chain_id: int,
    wallet_address: str,
    target: str,
    value: int,
    data: bytes,
    key_version: int,
) -> str:
    """
    Return the SHA-256 transaction-intent hash.

    Returns:
        64 lowercase hexadecimal characters.
    """

    encoded = build_transaction_intent(
        chain_id=chain_id,
        wallet_address=wallet_address,
        target=target,
        value=value,
        data=data,
        key_version=key_version,
    )

    return hashlib.sha256(encoded).hexdigest()
