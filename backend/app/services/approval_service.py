"""
HYQUB — Approval Service

Creates a signed ApprovalToken after a successful verifier quorum.

Flow:

    QuorumResult
        ↓
    Replay / expiry validation
        ↓
    ApprovalTokenPayload
        ↓
    Canonical SHA-256 hash
        ↓
    ECDSA signature
        ↓
    ApprovalToken
"""

from __future__ import annotations

from datetime import datetime, timezone

from app.crypto.approval import hash_approval_payload
from app.crypto.approval_signer import sign_approval_hash
from app.models.approval import ApprovalToken, ApprovalTokenPayload
from app.services.approval_validator import (
    ApprovalTiming,
    ApprovalValidationError,
    ApprovalValidator,
    UsedNonceStore,
)
from app.services.quorum_engine import QuorumResult


class ApprovalServiceError(Exception):
    """Raised when Approval Token creation fails."""


class ApprovalService:
    """
    Orchestrates the complete Approval Token creation pipeline.

    This service does not perform ML-DSA verification itself.
    It only acts after the quorum engine has produced a
    successful QuorumResult.
    """

    def __init__(
        self,
        validator: ApprovalValidator | None = None,
        nonce_store: UsedNonceStore | None = None,
    ) -> None:
        self._validator = validator or ApprovalValidator(
            nonce_store or UsedNonceStore()
        )

    def create_approval_token(
        self,
        *,
        wallet_address: str,
        message_hash: str,
        quorum_result: QuorumResult,
        nonce: int,
        issued_at: int,
        expires_at: int,
        now: datetime | None = None,
    ) -> ApprovalToken:
        """
        Create a signed ApprovalToken.

        The token can only be created when:
        - quorum is satisfied
        - key_version is known
        - nonce is valid
        - approval has not expired
        - nonce has not already been consumed
        """

        # ---------------------------------------------------------------
        # 1. Quorum must be satisfied
        # ---------------------------------------------------------------

        if not quorum_result.approved:
            raise ApprovalServiceError(
                "Cannot create approval token: quorum not satisfied"
            )

        if quorum_result.key_version is None:
            raise ApprovalServiceError(
                "Cannot create approval token: key version is unknown"
            )

        # ---------------------------------------------------------------
        # 2. Validate timing / replay protection
        # ---------------------------------------------------------------

        issued_dt = datetime.fromtimestamp(
            issued_at,
            tz=timezone.utc,
        )

        expires_dt = datetime.fromtimestamp(
            expires_at,
            tz=timezone.utc,
        )

        timing = ApprovalTiming(
            nonce=nonce,
            issued_at=issued_dt,
            expires_at=expires_dt,
        )

        try:
            self._validator.validate(
                timing,
                now=now,
            )
        except ApprovalValidationError as exc:
            raise ApprovalServiceError(
                f"Approval validation failed: {exc}"
            ) from exc

        # ---------------------------------------------------------------
        # 3. Build the approval payload
        # ---------------------------------------------------------------

        payload = ApprovalTokenPayload(
            wallet_address=wallet_address,
            message_hash=message_hash,
            key_version=quorum_result.key_version,
            nonce=nonce,
            issued_at=issued_at,
            expires_at=expires_at,
            verifier_ids=list(
                quorum_result.approving_verifier_ids
            ),
        )

        # ---------------------------------------------------------------
        # 4. Canonical payload hash
        # ---------------------------------------------------------------

        payload_hash = hash_approval_payload(payload)

        # ---------------------------------------------------------------
        # 5. ECDSA signature
        # ---------------------------------------------------------------

        signature = sign_approval_hash(payload_hash)

        # ---------------------------------------------------------------
        # 6. Return complete token
        # ---------------------------------------------------------------

        return ApprovalToken(
            payload=payload,
            signature=signature,
        )

    @staticmethod
    def verify_approval_token(
        token: ApprovalToken,
    ) -> bool:
        """
        Verify the structural integrity of an ApprovalToken.

        Recomputes the canonical payload hash and verifies the
        ECDSA signature against the configured approval signer.
        """

        # Recompute payload hash.
        expected_hash = hash_approval_payload(
            token.payload
        )

        # Recover and compare the signer.
        from eth_account import Account
        from eth_account.messages import encode_defunct

        from app.crypto.approval_signer import (
            get_approval_signer_address,
        )

        message = encode_defunct(
            primitive=bytes.fromhex(expected_hash)
        )

        try:
            recovered_address = Account.recover_message(
                message,
                signature=token.signature,
            )
        except Exception:
            return False

        expected_signer = get_approval_signer_address()

        return (
            recovered_address.lower()
            == expected_signer.lower()
        )
