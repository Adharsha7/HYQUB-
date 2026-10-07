"""
HYQUB — Ethereum Approval Signature Helpers

Signs the SHA-256 approval payload using Ethereum
personal-sign semantics.

The Solidity wallet verifies the resulting signature
using ecrecover().
"""

from __future__ import annotations

from eth_account import Account
from eth_account.messages import encode_defunct


def sign_approval_hash(
    approval_hash: str,
    private_key: str,
) -> str:
    """
    Sign a 32-byte approval hash using Ethereum personal-sign semantics.

    Args:
        approval_hash:
            64 hexadecimal characters, with or without 0x prefix.

        private_key:
            Ethereum private key used by the trusted approval signer.

    Returns:
        65-byte Ethereum signature as a 0x-prefixed hex string.

    Raises:
        ValueError:
            If approval_hash is not exactly 32 bytes.
    """

    clean_hash = approval_hash.removeprefix("0x")

    if len(clean_hash) != 64:
        raise ValueError(
            "approval_hash must contain exactly 32 bytes"
        )

    try:
        message_hash = bytes.fromhex(clean_hash)
    except ValueError as exc:
        raise ValueError(
            "approval_hash must be hexadecimal"
        ) from exc

    message = encode_defunct(primitive=message_hash)

    signed = Account.sign_message(
        message,
        private_key=private_key,
    )

    # Always return a 0x-prefixed hex string, consistent with
    # approval_signer.sign_approval_hash and with Solidity expectations.
    return "0x" + signed.signature.hex()


def recover_approval_signer(
    approval_hash: str,
    signature: str,
) -> str:
    """
    Recover the Ethereum address that signed an approval hash.

    This mirrors the Solidity verification flow:

        encode_defunct(approval_hash)
        -> ecrecover(...)
    """

    clean_hash = approval_hash.removeprefix("0x")
    clean_signature = signature.removeprefix("0x")

    if len(clean_hash) != 64:
        raise ValueError(
            "approval_hash must contain exactly 32 bytes"
        )

    try:
        message_hash = bytes.fromhex(clean_hash)
    except ValueError as exc:
        raise ValueError(
            "approval_hash must be hexadecimal"
        ) from exc

    try:
        signature_bytes = bytes.fromhex(clean_signature)
    except ValueError as exc:
        raise ValueError(
            "signature must be hexadecimal"
        ) from exc

    message = encode_defunct(primitive=message_hash)

    return Account.recover_message(
        message,
        signature=signature_bytes,
    )
