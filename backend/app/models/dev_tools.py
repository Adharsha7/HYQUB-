"""
HYQUB — Dev Tools Models
==========================

Models for DEVELOPMENT-ONLY endpoints that generate ML-DSA keypairs and
sign messages on the backend, purely so the frontend has something to
call before real browser-side ML-DSA (WASM) support exists.

These endpoints are NOT part of HYQUB's real security model. A real
deployment must never let the backend generate or hold a user's ML-DSA
private key — that defeats the entire point of a user-controlled
post-quantum signature. See api/dev_tools.py for how these are gated
out of any non-development environment.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class GenerateKeypairResponse(BaseModel):
    """
    A freshly generated ML-DSA-65 keypair, both base64-encoded.

    DEV ONLY. In a real deployment this key pair would be generated
    and held entirely client-side (or on dedicated user hardware),
    never touching the backend.
    """

    public_key: str = Field(..., description="Base64-encoded ML-DSA-65 public key.")
    secret_key: str = Field(..., description="Base64-encoded ML-DSA-65 secret key.")


class SignRequest(BaseModel):
    """
    DEV ONLY. Request to sign an arbitrary message with a supplied
    ML-DSA secret key. In a real deployment, this signing operation
    would happen entirely client-side; the secret key would never be
    transmitted to the backend at all.
    """

    secret_key: str = Field(..., min_length=1, description="Base64-encoded ML-DSA-65 secret key.")
    message: str = Field(..., min_length=1, description="The message to sign, as plain text.")


class SignResponse(BaseModel):
    """DEV ONLY. The resulting signature."""

    signature: str = Field(..., description="Base64-encoded ML-DSA-65 signature.")
