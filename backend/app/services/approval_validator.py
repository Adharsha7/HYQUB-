# app/services/approval_validator.py

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Set


class ApprovalValidationError(Exception):
    """Raised when an approval fails replay/expiry validation."""


@dataclass(frozen=True)
class ApprovalTiming:
    """
    Minimal view of an approval needed for replay + expiry checks.
    This is intentionally separate from the full approval payload model
    and from the ECDSA signing step — message_hash (the hash of the
    thing being authorized) is not touched here at all. This class only
    cares about nonce/issued_at/expires_at.
    """
    nonce: int
    issued_at: datetime
    expires_at: datetime


class UsedNonceStore:
    """
    Tracks nonces that have already been consumed.
    In-memory for now — swap for a DB/Redis-backed implementation
    later without changing the validator's interface.
    """

    def __init__(self) -> None:
        self._used: Set[int] = set()

    def is_used(self, nonce: int) -> bool:
        return nonce in self._used

    def mark_used(self, nonce: int) -> None:
        self._used.add(nonce)


class ApprovalValidator:
    """
    Stateless rule checks + stateful replay checks, kept explicit
    and separately testable.
    """

    def __init__(self, nonce_store: UsedNonceStore | None = None) -> None:
        self._nonce_store = nonce_store or UsedNonceStore()

    # --- stateless rules -------------------------------------------------

    @staticmethod
    def validate_nonce_format(nonce: int) -> None:
        if nonce < 0:
            raise ApprovalValidationError(f"nonce must be >= 0, got {nonce}")

    @staticmethod
    def validate_timing_order(timing: ApprovalTiming) -> None:
        if timing.expires_at <= timing.issued_at:
            raise ApprovalValidationError(
                "expires_at must be strictly after issued_at "
                f"(issued_at={timing.issued_at.isoformat()}, "
                f"expires_at={timing.expires_at.isoformat()})"
            )

    @staticmethod
    def validate_not_expired(timing: ApprovalTiming, now: datetime | None = None) -> None:
        now = now or datetime.now(timezone.utc)
        if now >= timing.expires_at:
            raise ApprovalValidationError(
                f"approval expired at {timing.expires_at.isoformat()} "
                f"(checked at {now.isoformat()})"
            )

    # --- stateful replay check --------------------------------------------

    def validate_not_replayed(self, timing: ApprovalTiming) -> None:
        if self._nonce_store.is_used(timing.nonce):
            raise ApprovalValidationError(f"nonce {timing.nonce} has already been used")

    def consume_nonce(self, timing: ApprovalTiming) -> None:
        """Call only after all other checks pass, to mark the nonce used."""
        self._nonce_store.mark_used(timing.nonce)

    # --- orchestration -----------------------------------------------------

    def validate(self, timing: ApprovalTiming, now: datetime | None = None) -> None:
        """
        Runs all checks in order and marks the nonce used on success.
        Does NOT touch message_hash or the approval payload's canonical
        hash — those belong to earlier/later stages of the pipeline.
        """
        self.validate_nonce_format(timing.nonce)
        self.validate_timing_order(timing)
        self.validate_not_expired(timing, now=now)
        self.validate_not_replayed(timing)
        self.consume_nonce(timing)
