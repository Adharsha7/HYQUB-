"""
HYQUB — Rotate Service
=========================

Orchestrates ML-DSA key rotation for an existing wallet.

Flow:

    Rotate Request
        ↓
    Look up wallet
        ↓
    Decode + validate new public key
        ↓
    Calculate new public-key hash (raw bytes)
        ↓
    Rotate key on blockchain
        ↓
    Read authoritative key_version from chain   ← Phase 1 fix (Task G)
        ↓
    Update local storage
        ↓
    Return new key version
"""

from __future__ import annotations

import hashlib
import logging

from app.crypto import mldsa
from app.crypto.encoding import decode_key_or_signature
from app.models.rotate import RotateKeyRequest, RotateKeyResponse
from app.utils.storage import WalletStorage
from app.utils.blockchain import get_key_version, rotate_wallet_on_chain


logger = logging.getLogger(__name__)


class WalletNotRegisteredError(Exception):
    """Raised when a rotation request targets an unregistered wallet."""

    def __init__(self, wallet_address: str):
        self.wallet_address = wallet_address
        super().__init__(f"Wallet is not registered: {wallet_address}")


class InvalidPublicKeyError(Exception):
    """
    Raised when new_ml_dsa_public_key is not valid base64, or does
    not decode to the expected ML-DSA-65 public key length. Fails
    before any blockchain call is made.
    """

    def __init__(self, reason: str):
        self.reason = reason
        super().__init__(f"Invalid ML-DSA public key: {reason}")


class BlockchainRotationError(Exception):
    """Raised when the on-chain key rotation transaction fails."""

    def __init__(self, wallet_address: str, original_error: Exception):
        self.wallet_address = wallet_address
        self.original_error = original_error

        super().__init__(
            f"On-chain rotation failed for {wallet_address}: {original_error}"
        )


class StorageDriftError(Exception):
    """
    Raised when blockchain rotation succeeds but local storage
    cannot be updated.
    """

    def __init__(
        self,
        wallet_address: str,
        new_key_version: int,
        original_error: Exception,
    ):
        self.wallet_address = wallet_address
        self.new_key_version = new_key_version
        self.original_error = original_error

        super().__init__(
            f"State drift for {wallet_address}: chain succeeded at "
            f"version {new_key_version} but local storage update failed: "
            f"{original_error}"
        )


def _validate_and_decode_public_key(ml_dsa_public_key: str) -> bytes:
    """
    Decode the base64 public key and confirm it is the right length
    for ML-DSA-65. Raises InvalidPublicKeyError on any problem.
    """
    try:
        key_bytes = decode_key_or_signature(
            ml_dsa_public_key, "new_ml_dsa_public_key"
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

    Matches register_service._hash_public_key exactly: both hash raw
    key bytes, not the base64 string. This keeps on-chain hashes
    consistent regardless of whether a key was set via /register or
    /rotate.
    """
    return hashlib.sha256(key_bytes).hexdigest()


def rotate_key(
    request: RotateKeyRequest,
    storage: WalletStorage,
) -> RotateKeyResponse:
    """
    Rotate a wallet's ML-DSA public key.

    New key is decoded and validated first. Blockchain is updated
    next. The new key_version is read from the chain (not computed
    locally) before local storage is updated.
    """

    # ---------------------------------------------------------
    # Step 1: Find existing wallet
    # ---------------------------------------------------------

    profile = storage.get(request.wallet_address)

    if profile is None:
        raise WalletNotRegisteredError(request.wallet_address)

    # ---------------------------------------------------------
    # Step 2: Decode + validate new public key BEFORE touching
    # the blockchain.
    # ---------------------------------------------------------

    new_key_bytes = _validate_and_decode_public_key(
        request.new_ml_dsa_public_key
    )

    # ---------------------------------------------------------
    # Step 3: Generate new public-key hash (raw bytes)
    # ---------------------------------------------------------

    new_key_hash = _hash_public_key(new_key_bytes)

    # ---------------------------------------------------------
    # Step 4: Rotate key on blockchain
    # ---------------------------------------------------------

    try:
        rotate_wallet_on_chain(
            wallet_address=request.wallet_address,
            new_key_hash=new_key_hash,
        )

    except Exception as exc:
        logger.error(
            "Blockchain rotation failed for %s: %s",
            request.wallet_address,
            exc,
        )

        raise BlockchainRotationError(
            request.wallet_address,
            exc,
        ) from exc

    # ---------------------------------------------------------
    # Step 5: Read authoritative key_version from the chain.
    #
    # We do NOT calculate (profile.key_version + 1) locally.
    # The contract is the single source of truth for key_version.
    # Reading it after the rotation confirms the transaction landed
    # and gives us the exact value the chain holds, regardless of
    # whether our in-memory profile was stale before rotation.
    # ---------------------------------------------------------

    try:
        chain_key_version = get_key_version(request.wallet_address)
    except Exception as exc:
        logger.critical(
            "STATE DRIFT: blockchain rotated wallet %s but reading "
            "key_version from chain failed: %s",
            request.wallet_address,
            exc,
        )
        raise StorageDriftError(
            request.wallet_address,
            profile.key_version + 1,  # best-effort estimate for the error message
            exc,
        ) from exc

    # ---------------------------------------------------------
    # Step 6: Update local storage
    # ---------------------------------------------------------

    updated_profile = profile.model_copy(
        update={
            "ml_dsa_public_key": request.new_ml_dsa_public_key,
            "ml_dsa_public_key_hash": new_key_hash,
            "key_version": chain_key_version,
        }
    )

    try:
        storage.update(
            request.wallet_address,
            updated_profile,
        )

    except Exception as exc:
        logger.critical(
            "STATE DRIFT: blockchain rotated wallet %s to "
            "version %s but local storage update failed: %s",
            request.wallet_address,
            chain_key_version,
            exc,
        )

        raise StorageDriftError(
            request.wallet_address,
            chain_key_version,
            exc,
        ) from exc

    # ---------------------------------------------------------
    # Step 7: Return response
    # ---------------------------------------------------------

    return RotateKeyResponse(
        success=True,
        message="Key rotation successful",
        key_version=chain_key_version,
    )
