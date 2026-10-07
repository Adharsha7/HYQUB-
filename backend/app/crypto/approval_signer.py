"""
HYQUB — ECDSA Approval Signer

Signs canonical Approval Token payload hashes using the
dedicated HYQUB approval-signing key.

This key is intentionally separate from the blockchain
registrar key.
"""

from __future__ import annotations

from eth_account import Account
from eth_account.messages import encode_defunct

from app.config import get_settings


def get_approval_signer_address() -> str:
    """Return the Ethereum address of the approval signer."""

    settings = get_settings()

    account = Account.from_key(
        settings.approval_signer_private_key
    )

    return account.address


def sign_approval_hash(payload_hash: str) -> str:
    """
    Sign an approval payload hash using the dedicated
    ECDSA approval signer.

    Returns:
        0x-prefixed Ethereum-compatible signature.
    """

    if not isinstance(payload_hash, str):
        raise ValueError("payload_hash must be a string")

    clean_hash = (
        payload_hash[2:]
        if payload_hash.startswith("0x")
        else payload_hash
    )

    if len(clean_hash) != 64:
        raise ValueError(
            "payload_hash must contain exactly 32 bytes"
        )

    try:
        hash_bytes = bytes.fromhex(clean_hash)
    except ValueError as exc:
        raise ValueError(
            "payload_hash must be valid hexadecimal"
        ) from exc

    settings = get_settings()

    account = Account.from_key(
        settings.approval_signer_private_key
    )

    message = encode_defunct(
        primitive=hash_bytes
    )

    signed = account.sign_message(message)

    return "0x" + signed.signature.hex()
    
