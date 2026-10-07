"""
HYQUB — Register Service

Orchestrates wallet registration across:
    1. Backend security profile
    2. HYQUBRegistry smart contract

The service does not know about HTTP or FastAPI.
"""

from __future__ import annotations

import hashlib

from app.crypto import mldsa
from app.crypto.encoding import decode_key_or_signature
from app.models.register import (
    RegisterRequest,
    RegisterResponse,
    SecurityProfile,
)
from app.utils.storage import WalletAlreadyExistsError, WalletStorage
from app.utils.blockchain import get_key_version, register_wallet_on_chain


class WalletAlreadyRegisteredError(Exception):
    """Raised when a wallet is already registered."""

    def __init__(self, wallet_address: str):
        self.wallet_address = wallet_address
        super().__init__(
            f"Wallet is already registered: {wallet_address}"
        )


class InvalidPublicKeyError(Exception):
    """
    Raised when ml_dsa_public_key is not valid base64, or does not
    decode to the expected ML-DSA-65 public key length. This is a
    deliberate hard failure at registration time — better to reject
    here than silently store a key that will fail every future
    /verify call.
    """

    def __init__(self, reason: str):
        self.reason = reason
        super().__init__(f"Invalid ML-DSA public key: {reason}")


def _validate_and_decode_public_key(ml_dsa_public_key: str) -> bytes:
    """
    Decode the base64 public key and confirm it is the right length
    for ML-DSA-65. Raises InvalidPublicKeyError on any problem.
    """
    try:
        key_bytes = decode_key_or_signature(
            ml_dsa_public_key, "ml_dsa_public_key"
        )
    except ValueError as exc:
        raise InvalidPublicKeyError(str(exc)) from exc

    expected_len = mldsa.get_public_key_length()
    if len(key_bytes) != expected_len:
        raise InvalidPublicKeyError(
            f"expected {expected_len} bytes, got {len(key_bytes)} bytes"
        )

    return key_bytes


def _hash_public_key(key_bytes: bytes) -> str:
    """
    Create SHA-256 fingerprint of the decoded ML-DSA public key bytes.

    NOTE: this hashes the raw key material, not the base64 string
    representation of it — this is the value committed on-chain, so
    it must be reproducible by anyone who has the raw public key,
    independent of how HYQUB happens to serialize it over HTTP.
    """
    return hashlib.sha256(key_bytes).hexdigest()


def register_wallet(
    request: RegisterRequest,
    storage: WalletStorage,
) -> RegisterResponse:
    """
    Register a wallet locally and on the HYQUBRegistry blockchain.

    Flow:

        Request
          ↓
        Decode + validate public key
          ↓
        Check existing wallet
          ↓
        Hash public key (raw bytes)
          ↓
        Blockchain registration
          ↓
        Local storage
          ↓
        Response with transaction hash
    """

    # ---------------------------------------------------------
    # Step 1: Validate and decode the public key BEFORE anything
    # else — fail fast, before touching storage or the chain.
    # ---------------------------------------------------------

    key_bytes = _validate_and_decode_public_key(
        request.ml_dsa_public_key
    )

    # ---------------------------------------------------------
    # Step 2: Check whether wallet already exists
    # ---------------------------------------------------------

    if storage.get(request.wallet_address) is not None:
        raise WalletAlreadyRegisteredError(
            request.wallet_address
        )

    # ---------------------------------------------------------
    # Step 3: Register wallet on blockchain (or detect it's already
    # registered there — see register_wallet_on_chain's docstring).
    # ---------------------------------------------------------

    key_hash = _hash_public_key(key_bytes)

    transaction_hash = register_wallet_on_chain(
        wallet_address=request.wallet_address,
        key_hash=key_hash,
    )

    if transaction_hash is None:
        # Already registered on-chain (likely: backend restarted and
        # lost its in-memory record, but on-chain state is permanent).
        # Trust the chain's real key_version rather than assuming 1,
        # and proceed to sync local storage with the newly-submitted
        # public key material.
        key_version = get_key_version(request.wallet_address)
        message = (
            "Wallet was already registered on-chain; "
            "local record synced with the on-chain key_version"
        )
    else:
        key_version = 1
        message = "Registration successful"

    # ---------------------------------------------------------
    # Step 4: Generate Security Profile
    # ---------------------------------------------------------

    profile = SecurityProfile(
        wallet_address=request.wallet_address,
        ml_dsa_public_key=request.ml_dsa_public_key,
        ml_dsa_public_key_hash=key_hash,
        key_version=key_version,
    )

    # ---------------------------------------------------------
    # Step 5: Store profile locally
    # ---------------------------------------------------------

    try:
        storage.add(
            request.wallet_address,
            profile,
        )

    except WalletAlreadyExistsError as exc:
        raise WalletAlreadyRegisteredError(
            request.wallet_address
        ) from exc

    # ---------------------------------------------------------
    # Step 6: Return response
    # ---------------------------------------------------------

    return RegisterResponse(
        success=True,
        message=message,
        key_version=profile.key_version,
        transaction_hash=transaction_hash,
    )
