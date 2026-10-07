"""
HYQUB — Quorum Engine

Phase 2:
Aggregates independent VerificationResults from multiple PQVerifier
instances and decides whether quorum was reached.

This module does not:
- perform cryptography itself (that's mldsa.py / verifier_engine.py)
- talk to FastAPI
- issue Approval Tokens
- modify blockchain state

It only aggregates already-computed results into a quorum decision.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.services.verifier_engine import VerificationResult


@dataclass(frozen=True)
class QuorumResult:
    """
    Outcome of aggregating multiple VerificationResults.

    approved:
        True if at least `required_quorum` verifiers independently
        verified the signature AND all results agree on key_version.

    approving_verifier_ids:
        IDs of verifiers whose result was verified=True.

    total_verifiers:
        Total number of results considered.

    required_quorum:
        The quorum threshold that was applied.

    key_version:
        The key_version being verified, IF all results agreed on it.
        None if results disagreed on key_version (a distinct failure
        mode — this is not the same as quorum simply not being met).
    """

    approved: bool
    approving_verifier_ids: tuple[str, ...]
    total_verifiers: int
    required_quorum: int
    key_version: int | None


class KeyVersionMismatchError(Exception):
    """
    Raised when the VerificationResults being aggregated disagree on
    key_version. This should not happen in normal operation — it
    indicates verifiers checked the signature against different key
    versions (e.g. a race with a concurrent key rotation), and
    quorum cannot be meaningfully evaluated across incompatible
    checks.
    """

    def __init__(self, key_versions: set[int]):
        self.key_versions = key_versions
        super().__init__(
            f"VerificationResults disagree on key_version: {sorted(key_versions)}"
        )


def evaluate_quorum(
    results: list[VerificationResult],
    required_quorum: int,
) -> QuorumResult:
    """
    Aggregate independent VerificationResults into a quorum decision.

    Raises:
        ValueError: if results is empty, or required_quorum < 1.
        KeyVersionMismatchError: if results disagree on key_version.
    """

    if not results:
        raise ValueError("results must not be empty")

    if required_quorum < 1:
        raise ValueError("required_quorum must be at least 1")

    key_versions = {r.key_version for r in results}
    if len(key_versions) > 1:
        raise KeyVersionMismatchError(key_versions)

    key_version = next(iter(key_versions))

    approving_ids = tuple(
        r.verifier_id for r in results if r.verified
    )

    approved = len(approving_ids) >= required_quorum

    return QuorumResult(
        approved=approved,
        approving_verifier_ids=approving_ids,
        total_verifiers=len(results),
        required_quorum=required_quorum,
        key_version=key_version,
    )
