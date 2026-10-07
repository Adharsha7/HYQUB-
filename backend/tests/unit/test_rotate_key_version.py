"""
HYQUB — rotate_service key_version regression tests  (Task G)

Verifies that after a successful on-chain key rotation, the stored
key_version is read from the blockchain rather than calculated locally
as (profile.key_version + 1).

All blockchain calls are mocked — no live Anvil required.

Regression scenario:
    If the in-memory profile has key_version=N but the chain already
    has key_version=N+k (e.g. because the backend was restarted and
    the wallet was re-synced with a stale local version), the old code
    would store N+1 while the chain holds N+k+1.  The new code reads
    the chain and stores exactly what the chain reports.
"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import patch, MagicMock

import pytest

from app.crypto.mldsa import generate_keypair
from app.crypto.encoding import encode_key_or_signature
from app.models.register import SecurityProfile
from app.models.rotate import RotateKeyRequest
from app.services.rotate_service import (
    BlockchainRotationError,
    InvalidPublicKeyError,
    StorageDriftError,
    WalletNotRegisteredError,
    rotate_key,
)
from app.utils.storage import InMemoryWalletStorage


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

WALLET_ADDR = "0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"


def _fresh_keypair_b64() -> str:
    pk_bytes, _ = generate_keypair()
    return encode_key_or_signature(pk_bytes)


def _make_profile(key_version: int = 1) -> SecurityProfile:
    pk_bytes, _ = generate_keypair()
    pk_b64 = encode_key_or_signature(pk_bytes)
    return SecurityProfile(
        wallet_address=WALLET_ADDR,
        ml_dsa_public_key=pk_b64,
        ml_dsa_public_key_hash="a" * 64,
        key_version=key_version,
        registered_at=datetime.now(timezone.utc),
    )


def _storage_with_profile(profile: SecurityProfile) -> InMemoryWalletStorage:
    store = InMemoryWalletStorage()
    store.add(WALLET_ADDR, profile)
    return store


# ---------------------------------------------------------------------------
# Core regression: key_version must come from the chain
# ---------------------------------------------------------------------------

class TestKeyVersionFromChain:

    def test_key_version_is_read_from_chain_not_calculated(self):
        """
        After a successful rotation the stored key_version must equal
        what get_key_version() returns, NOT profile.key_version + 1.
        """
        profile = _make_profile(key_version=1)
        store = _storage_with_profile(profile)
        new_pk_b64 = _fresh_keypair_b64()
        request = RotateKeyRequest(
            wallet_address=WALLET_ADDR,
            new_ml_dsa_public_key=new_pk_b64,
        )

        # Chain reports key_version=2 after rotation (the normal case).
        with patch("app.services.rotate_service.rotate_wallet_on_chain") as mock_rotate, \
             patch("app.services.rotate_service.get_key_version", return_value=2) as mock_kv:

            mock_rotate.return_value = "0x" + "ab" * 32   # fake tx hash

            response = rotate_key(request, store)

        assert response.key_version == 2
        assert mock_kv.called

        # Confirm the stored profile also has the chain value
        stored = store.get(WALLET_ADDR)
        assert stored is not None
        assert stored.key_version == 2

    def test_stale_local_version_is_overridden_by_chain(self):
        """
        Regression scenario: local profile has key_version=1 but chain
        already has key_version=3 (e.g. two rotations happened while the
        backend was restarted).  After the next rotation the chain will
        report key_version=4; the service must store 4, not 2.
        """
        profile = _make_profile(key_version=1)   # stale — chain is at 3
        store = _storage_with_profile(profile)
        new_pk_b64 = _fresh_keypair_b64()
        request = RotateKeyRequest(
            wallet_address=WALLET_ADDR,
            new_ml_dsa_public_key=new_pk_b64,
        )

        # Chain reports key_version=4 (stale local was 1, but chain was 3→4)
        with patch("app.services.rotate_service.rotate_wallet_on_chain") as mock_rotate, \
             patch("app.services.rotate_service.get_key_version", return_value=4):

            mock_rotate.return_value = "0x" + "cd" * 32

            response = rotate_key(request, store)

        assert response.key_version == 4

        stored = store.get(WALLET_ADDR)
        assert stored.key_version == 4

    def test_chain_version_used_for_storage_update(self):
        """
        The chain key_version must be used when building the updated
        SecurityProfile, not the pre-rotation local value.
        """
        profile = _make_profile(key_version=5)
        store = _storage_with_profile(profile)
        new_pk_b64 = _fresh_keypair_b64()
        request = RotateKeyRequest(
            wallet_address=WALLET_ADDR,
            new_ml_dsa_public_key=new_pk_b64,
        )

        with patch("app.services.rotate_service.rotate_wallet_on_chain"), \
             patch("app.services.rotate_service.get_key_version", return_value=6):

            response = rotate_key(request, store)

        # Must be 6 (chain value), not 6 == 5+1 only by coincidence.
        # The old code would also produce 6 here, but would fail the
        # stale test above. This test ensures the happy path still works.
        assert response.key_version == 6
        stored = store.get(WALLET_ADDR)
        assert stored.key_version == 6

    def test_new_public_key_stored_alongside_chain_version(self):
        """
        The updated profile must contain the NEW public key with the
        chain-sourced key_version.
        """
        profile = _make_profile(key_version=1)
        store = _storage_with_profile(profile)
        new_pk_b64 = _fresh_keypair_b64()
        request = RotateKeyRequest(
            wallet_address=WALLET_ADDR,
            new_ml_dsa_public_key=new_pk_b64,
        )

        with patch("app.services.rotate_service.rotate_wallet_on_chain"), \
             patch("app.services.rotate_service.get_key_version", return_value=2):

            rotate_key(request, store)

        stored = store.get(WALLET_ADDR)
        assert stored.ml_dsa_public_key == new_pk_b64
        assert stored.key_version == 2


# ---------------------------------------------------------------------------
# Error path: chain read fails after rotation
# ---------------------------------------------------------------------------

class TestChainReadFailure:

    def test_raises_storage_drift_if_chain_read_fails(self):
        """
        If rotate_wallet_on_chain succeeds but get_key_version raises,
        a StorageDriftError must be raised so the operator knows the
        on-chain state advanced but local storage was not updated.
        """
        profile = _make_profile(key_version=1)
        store = _storage_with_profile(profile)
        new_pk_b64 = _fresh_keypair_b64()
        request = RotateKeyRequest(
            wallet_address=WALLET_ADDR,
            new_ml_dsa_public_key=new_pk_b64,
        )

        with patch("app.services.rotate_service.rotate_wallet_on_chain"), \
             patch("app.services.rotate_service.get_key_version",
                   side_effect=RuntimeError("RPC offline")):

            with pytest.raises(StorageDriftError):
                rotate_key(request, store)

    def test_local_storage_not_updated_if_chain_read_fails(self):
        """
        If the chain read fails, the local profile must remain unchanged
        (don't partially update it).
        """
        original_profile = _make_profile(key_version=1)
        original_pk = original_profile.ml_dsa_public_key
        store = _storage_with_profile(original_profile)
        new_pk_b64 = _fresh_keypair_b64()
        request = RotateKeyRequest(
            wallet_address=WALLET_ADDR,
            new_ml_dsa_public_key=new_pk_b64,
        )

        with patch("app.services.rotate_service.rotate_wallet_on_chain"), \
             patch("app.services.rotate_service.get_key_version",
                   side_effect=RuntimeError("RPC offline")):

            with pytest.raises(StorageDriftError):
                rotate_key(request, store)

        # Profile must be unchanged
        stored = store.get(WALLET_ADDR)
        assert stored.key_version == 1
        assert stored.ml_dsa_public_key == original_pk


# ---------------------------------------------------------------------------
# Existing error paths still work
# ---------------------------------------------------------------------------

class TestExistingErrorPaths:

    def test_raises_wallet_not_registered(self):
        store = InMemoryWalletStorage()   # empty
        new_pk_b64 = _fresh_keypair_b64()
        request = RotateKeyRequest(
            wallet_address=WALLET_ADDR,
            new_ml_dsa_public_key=new_pk_b64,
        )
        with pytest.raises(WalletNotRegisteredError):
            rotate_key(request, store)

    def test_raises_invalid_public_key_on_bad_base64(self):
        profile = _make_profile()
        store = _storage_with_profile(profile)
        request = RotateKeyRequest(
            wallet_address=WALLET_ADDR,
            new_ml_dsa_public_key="not-valid-base64!!!",
        )
        with pytest.raises(InvalidPublicKeyError):
            rotate_key(request, store)

    def test_raises_blockchain_rotation_error_on_chain_failure(self):
        profile = _make_profile()
        store = _storage_with_profile(profile)
        new_pk_b64 = _fresh_keypair_b64()
        request = RotateKeyRequest(
            wallet_address=WALLET_ADDR,
            new_ml_dsa_public_key=new_pk_b64,
        )
        with patch("app.services.rotate_service.rotate_wallet_on_chain",
                   side_effect=RuntimeError("contract reverted")):
            with pytest.raises(BlockchainRotationError):
                rotate_key(request, store)

    def test_get_key_version_not_called_if_blockchain_rotation_fails(self):
        """get_key_version must not be called if the chain rotation itself fails."""
        profile = _make_profile()
        store = _storage_with_profile(profile)
        new_pk_b64 = _fresh_keypair_b64()
        request = RotateKeyRequest(
            wallet_address=WALLET_ADDR,
            new_ml_dsa_public_key=new_pk_b64,
        )
        with patch("app.services.rotate_service.rotate_wallet_on_chain",
                   side_effect=RuntimeError("revert")), \
             patch("app.services.rotate_service.get_key_version") as mock_kv:

            with pytest.raises(BlockchainRotationError):
                rotate_key(request, store)

            # Chain read must not have been attempted
            mock_kv.assert_not_called()

    def test_storage_drift_error_on_storage_update_failure(self):
        """If chain rotation + chain read both succeed but storage.update raises,
        StorageDriftError must be raised."""
        profile = _make_profile(key_version=1)
        new_pk_b64 = _fresh_keypair_b64()
        request = RotateKeyRequest(
            wallet_address=WALLET_ADDR,
            new_ml_dsa_public_key=new_pk_b64,
        )

        # Use a real storage instance but make update() fail
        store = _storage_with_profile(profile)
        original_update = store.update
        store.update = MagicMock(side_effect=RuntimeError("disk full"))

        with patch("app.services.rotate_service.rotate_wallet_on_chain"), \
             patch("app.services.rotate_service.get_key_version", return_value=2):

            with pytest.raises(StorageDriftError) as exc_info:
                rotate_key(request, store)

        # The drift error must carry the chain value, not a local guess
        assert exc_info.value.new_key_version == 2
