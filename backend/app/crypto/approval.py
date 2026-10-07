"""
HYQUB — Approval Token Cryptographic Helpers

Provides deterministic hashing for ApprovalTokenPayload.

The payload is serialized using standard Ethereum ABI encoding
so that Python and Solidity produce identical bytes before
SHA-256 hashing.
"""

from __future__ import annotations

import hashlib

from eth_abi import encode

from app.models.approval import ApprovalTokenPayload


DOMAIN = "HYQUB_APPROVAL_V1"


def canonicalize_payload(
    payload: ApprovalTokenPayload,
) -> bytes:
    """
    Serialize the approval payload using the exact ABI encoding
    used by Solidity ApprovalPayload.t.sol.

    Solidity ground truth:

        abi.encode(
            "HYQUB_APPROVAL_V1",
            wallet,
            messageHash,
            keyVersion,
            nonce,
            issuedAt,
            verifierIds
        )

    NOTE:
        expires_at is intentionally NOT included here because
        the current Solidity approval payload does not include it.
        Expiry can be added later as a separate protocol change.
    """

    return encode(
        [
            "string",
            "address",
            "bytes32",
            "uint256",
            "uint256",
            "uint256",
            "string[]",
        ],
        [
            DOMAIN,
            payload.wallet_address,
            bytes.fromhex(
                payload.message_hash.removeprefix("0x")
            ),
            payload.key_version,
            payload.nonce,
            payload.issued_at,
            payload.verifier_ids,
        ],
    )


def hash_approval_payload(
    payload: ApprovalTokenPayload,
) -> str:
    """
    Return the SHA-256 hash of the canonical ABI payload.

    Returns:
        Lowercase hexadecimal string without 0x prefix.
    """

    canonical_bytes = canonicalize_payload(payload)

    return hashlib.sha256(
        canonical_bytes
    ).hexdigest()
