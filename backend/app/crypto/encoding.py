"""
HYQUB — Base64 Encoding Helpers

Single source of truth for how key/signature bytes are represented
as strings over HTTP. HYQUB uses standard base64 (RFC 4648), not hex,
not URL-safe base64. Every model (register, rotate, verify) and every
service that touches ml_dsa_public_key / signature fields should go
through these two functions rather than calling base64 directly.
"""

from __future__ import annotations

import base64
import binascii


def decode_key_or_signature(value: str, field_name: str) -> bytes:
    """
    Decode a base64-encoded key or signature string to raw bytes.

    Raises:
        ValueError: if value is not valid base64.
    """
    try:
        return base64.b64decode(value, validate=True)
    except (binascii.Error, ValueError) as e:
        raise ValueError(f"{field_name} is not valid base64") from e


def encode_key_or_signature(value: bytes) -> str:
    """Encode raw key or signature bytes as a base64 string."""
    return base64.b64encode(value).decode("ascii")
