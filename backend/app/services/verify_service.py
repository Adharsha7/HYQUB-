"""
HYQUB — Verify Service

Orchestrates wallet signature verification through the
PQ Verification Engine.
"""

from __future__ import annotations

from app.config import get_settings
from app.models.verify import VerifyRequest, VerifyResponse
from app.services.verifier_engine import PQVerifier
from app.utils.storage import WalletStorage


class WalletNotRegisteredError(Exception):
    """Raised when a verification request targets an unregistered wallet."""

    def __init__(self, wallet_address: str):
        self.wallet_address = wallet_address
        super().__init__(
            f"Wallet is not registered: {wallet_address}"
        )


def verify_wallet_signature(
    request: VerifyRequest,
    storage: WalletStorage,
) -> VerifyResponse:
    """
    Verify a wallet's ML-DSA signature through PQVerifier.
    """

    profile = storage.get(request.wallet_address)

    if profile is None:
        raise WalletNotRegisteredError(
            request.wallet_address
        )

    settings = get_settings()
    verifier = PQVerifier(
        verifier_id=settings.verifier_id
    )

    result = verifier.verify(
        public_key=profile.ml_dsa_public_key,
        message=request.message,
        signature=request.signature,
        key_version=profile.key_version,
    )

    return VerifyResponse(
        verified=result.verified,
        message=(
            "Signature verified successfully"
            if result.verified
            else "Signature verification failed"
        ),
    )
