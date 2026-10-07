"""
HYQUB — PQ Verifier Engine

Phase 2:
Provides a clean verification layer above the existing
ML-DSA-65 crypto implementation.

This module does not:
- talk to FastAPI
- modify blockchain state
- generate approval tokens
- implement quorum yet

It only performs a structured ML-DSA verification.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.crypto import mldsa
from app.crypto.encoding import decode_key_or_signature


@dataclass(frozen=True)
class VerificationResult:
    """
    Result returned by a HYQUB verifier.

    verified:
        Whether the ML-DSA signature is valid.

    verifier_id:
        Identifier of the verifier that performed the check.

    algorithm:
        Cryptographic algorithm used.

    key_version:
        Version of the wallet key being verified.
    """

    verified: bool
    verifier_id: str
    algorithm: str
    key_version: int


class PQVerifier:
    """
    HYQUB post-quantum signature verifier.

    This is the abstraction that will later allow us to run
    independent Verifier A and Verifier B instances.
    """

    def __init__(
        self,
        verifier_id: str,
    ) -> None:
        if not verifier_id:
            raise ValueError("verifier_id must not be empty")

        self.verifier_id = verifier_id

    def verify(
        self,
        *,
        public_key: str,
        message: str,
        signature: str,
        key_version: int,
    ) -> VerificationResult:
        """
        Verify an ML-DSA-65 signature.

        Invalid Base64, invalid key material, malformed signatures,
        and failed cryptographic verification all produce
        verified=False rather than raising.
        """

        try:
            public_key_bytes = decode_key_or_signature(
                public_key,
                "public_key",
            )

            signature_bytes = decode_key_or_signature(
                signature,
                "signature",
            )

        except ValueError:
            return VerificationResult(
                verified=False,
                verifier_id=self.verifier_id,
                algorithm=mldsa.ALGORITHM,
                key_version=key_version,
            )

        verified = mldsa.verify(
            message.encode("utf-8"),
            signature_bytes,
            public_key_bytes,
        )

        return VerificationResult(
            verified=verified,
            verifier_id=self.verifier_id,
            algorithm=mldsa.ALGORITHM,
            key_version=key_version,
        )
