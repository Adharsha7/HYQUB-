"""
HYQUB — ML-DSA-65 Crypto Module

Real post-quantum digital signatures using liboqs.
"""

from __future__ import annotations

import oqs


ALGORITHM = "ML-DSA-65"


with oqs.Signature(ALGORITHM) as _sig:
    PUBLIC_KEY_LEN = _sig.details["length_public_key"]
    SECRET_KEY_LEN = _sig.details["length_secret_key"]
    SIGNATURE_MAX_LEN = _sig.details["length_signature"]


def generate_keypair() -> tuple[bytes, bytes]:
    """Generate an ML-DSA-65 public/secret key pair."""
    with oqs.Signature(ALGORITHM) as signer:
        public_key = signer.generate_keypair()
        secret_key = signer.export_secret_key()

    return public_key, secret_key


def sign(message: bytes, secret_key: bytes) -> bytes:
    """Sign a non-empty message using an ML-DSA-65 secret key."""
    if not isinstance(message, bytes) or not message:
        raise ValueError("message must be non-empty bytes")

    if not isinstance(secret_key, bytes):
        raise ValueError("secret_key must be bytes")

    if len(secret_key) != SECRET_KEY_LEN:
        raise ValueError(
            f"invalid secret key length: expected {SECRET_KEY_LEN} bytes"
        )

    with oqs.Signature(ALGORITHM, secret_key) as signer:
        return signer.sign(message)


def verify(
    message: bytes,
    signature: bytes,
    public_key: bytes,
) -> bool:
    """Verify an ML-DSA-65 signature."""

    if not isinstance(message, bytes) or not message:
        return False

    if not isinstance(signature, bytes):
        return False

    if not isinstance(public_key, bytes):
        return False

    if len(public_key) != PUBLIC_KEY_LEN:
        return False

    if len(signature) > SIGNATURE_MAX_LEN:
        return False

    try:
        with oqs.Signature(ALGORITHM) as verifier:
            return verifier.verify(message, signature, public_key)
    except Exception:
        return False


def get_public_key_length() -> int:
    """Return the expected ML-DSA-65 public key length in bytes."""
    with oqs.Signature(ALGORITHM) as signer:
        return signer.details["length_public_key"]
