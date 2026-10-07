"""
HYQUB — Storage Layer
=======================

Sole responsibility: store and retrieve Security Profiles, keyed by
wallet address.

This module does NOT:
    - verify ML-DSA signatures
    - handle FastAPI requests
    - perform any cryptography
    - return HTTP responses

Architecture:

    Register Service
        ↓ depends on
    WalletStorage (abstract interface)
        ↑ implemented by
    InMemoryWalletStorage (today)
    PostgresWalletStorage (future — not implemented here)

The service layer must only ever type-hint against `WalletStorage`,
never against `InMemoryWalletStorage` directly. That's what makes the
backing store swappable later without touching the service.
"""

from __future__ import annotations

import threading
from abc import ABC, abstractmethod
from typing import Optional

from app.models.register import SecurityProfile


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class WalletAlreadyExistsError(Exception):
    """Raised by add() when the wallet_address is already registered."""

    def __init__(self, wallet_address: str):
        self.wallet_address = wallet_address
        super().__init__(f"Wallet already registered: {wallet_address}")


class WalletNotFoundError(Exception):
    """Raised by update() when the wallet_address has no existing profile."""

    def __init__(self, wallet_address: str):
        self.wallet_address = wallet_address
        super().__init__(f"Wallet not found: {wallet_address}")


# ---------------------------------------------------------------------------
# Abstract interface
# ---------------------------------------------------------------------------

class WalletStorage(ABC):
    """
    Abstract contract for wallet Security Profile storage.

    Every backing implementation (in-memory dict, Postgres, Redis, ...)
    must implement this exact interface. The rest of the application
    (register_service.py, verify_service.py, etc.) depends only on this
    abstraction.
    """

    @abstractmethod
    def add(self, wallet_address: str, profile: SecurityProfile) -> None:
        """
        Store a new SecurityProfile for a wallet that is not yet registered.

        Raises:
            WalletAlreadyExistsError: if wallet_address is already present.
        """
        raise NotImplementedError

    @abstractmethod
    def get(self, wallet_address: str) -> Optional[SecurityProfile]:
        """
        Retrieve the SecurityProfile for a wallet.

        Returns:
            The SecurityProfile if found, otherwise None. Never raises
            for a missing wallet — absence is a normal, expected outcome.
        """
        raise NotImplementedError

    @abstractmethod
    def exists(self, wallet_address: str) -> bool:
        """Return True if a profile is already stored for this wallet."""
        raise NotImplementedError

    @abstractmethod
    def update(self, wallet_address: str, profile: SecurityProfile) -> None:
        """
        Replace the existing SecurityProfile for a wallet (e.g. key rotation).

        Raises:
            WalletNotFoundError: if wallet_address has no existing profile.
        """
        raise NotImplementedError

    @abstractmethod
    def delete(self, wallet_address: str) -> None:
        """
        Hard-delete a wallet's profile.

        Note: for revocation, prefer update() with status=REVOKED instead
        of delete() — revocation should usually be a status change, not a
        disappearance. delete() is here for genuine removal (e.g. test
        cleanup, or a future GDPR-style erasure request).

        Raises:
            WalletNotFoundError: if wallet_address has no existing profile.
        """
        raise NotImplementedError

    @abstractmethod
    def list_all(self) -> list[SecurityProfile]:
        """
        Return every stored profile.

        Debug/development convenience only — not intended for production
        API exposure (no pagination, no filtering).
        """
        raise NotImplementedError


# ---------------------------------------------------------------------------
# In-memory implementation
# ---------------------------------------------------------------------------

class InMemoryWalletStorage(WalletStorage):
    """
    Dictionary-backed implementation of WalletStorage.

    {
        "0x123...": SecurityProfile(...),
        "0x456...": SecurityProfile(...),
    }

    Lookups, inserts, and updates are O(1). A lock guards all mutating
    operations since FastAPI may serve concurrent requests across async
    tasks/threads and a plain dict is not thread-safe.

    Known limitation: get() returns the stored object by reference, not
    a copy. A caller that mutates the returned SecurityProfile in place
    bypasses update() and silently changes stored state. A real
    database-backed implementation would not have this issue, since each
    get() would deserialize a fresh object. Treat returned profiles as
    read-only unless going through update().
    """

    def __init__(self) -> None:
        self._profiles: dict[str, SecurityProfile] = {}
        self._lock = threading.Lock()

    def add(self, wallet_address: str, profile: SecurityProfile) -> None:
        with self._lock:
            if wallet_address in self._profiles:
                raise WalletAlreadyExistsError(wallet_address)
            self._profiles[wallet_address] = profile

    def get(self, wallet_address: str) -> Optional[SecurityProfile]:
        # Read-only; no lock needed for a single dict.get() in CPython,
        # but we take it anyway for consistency and to stay correct if
        # the implementation ever grows beyond a single dict access.
        with self._lock:
            return self._profiles.get(wallet_address)

    def exists(self, wallet_address: str) -> bool:
        with self._lock:
            return wallet_address in self._profiles

    def update(self, wallet_address: str, profile: SecurityProfile) -> None:
        with self._lock:
            if wallet_address not in self._profiles:
                raise WalletNotFoundError(wallet_address)
            self._profiles[wallet_address] = profile

    def delete(self, wallet_address: str) -> None:
        with self._lock:
            if wallet_address not in self._profiles:
                raise WalletNotFoundError(wallet_address)
            del self._profiles[wallet_address]

    def list_all(self) -> list[SecurityProfile]:
        with self._lock:
            return list(self._profiles.values())


# ---------------------------------------------------------------------------
# Shared singleton instance
# ---------------------------------------------------------------------------
#
# The rest of the application (API routes, services) should import this
# `storage` object rather than instantiating InMemoryWalletStorage
# themselves. Instantiating it per-request would create a fresh, empty
# dictionary on every call — losing every previously registered wallet.
#
# When Postgres (or any other backend) replaces the in-memory store,
# this is the only line that changes:
#
#     storage = PostgreSQLWalletStorage(dsn=...)
#
# Nothing importing `storage` needs to change, since it only ever
# depends on the WalletStorage interface.

storage: WalletStorage = InMemoryWalletStorage()
