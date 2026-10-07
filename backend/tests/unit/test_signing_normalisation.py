"""
HYQUB — Signing Output Normalisation Regression Tests  (Task F)

Verifies that:
1. signing.sign_approval_hash returns a 0x-prefixed 130-char hex string.
2. approval_signer.sign_approval_hash returns the same format.
3. Both produce byte-identical signatures for the same input and key.
4. recover_approval_signer correctly recovers the signer from both.
5. The Solidity compatibility vector from ApprovalSignature.t.sol and
   PythonSignatureCompatibility.t.sol is not broken.

CRITICAL CONSTRAINTS (must not be violated):
- The signed bytes are NOT changed.
- The hash bytes are NOT changed.
- The EIP-191 message wrapping is NOT changed.
- The signature algorithm is NOT changed.
- Solidity recovery behaviour is NOT changed.
Only the *string representation* of the returned signature is normalised
to always include the 0x prefix.
"""

from __future__ import annotations

from eth_account import Account

from app.crypto.signing import sign_approval_hash, recover_approval_signer


# ---------------------------------------------------------------------------
# Deterministic test key — used only in these unit tests.
# This is Anvil's well-known account #4 private key; it is public knowledge
# and safe to use in test vectors.  NEVER use it for real funds.
# ---------------------------------------------------------------------------
_TEST_PRIVATE_KEY = "0x47e179ec197488593b187f80a00eb0da91f1b9d0b13f8733639f19c30a34926a"
_TEST_SIGNER_ADDRESS = Account.from_key(_TEST_PRIVATE_KEY).address


class TestSigningReturnFormat:
    """signing.sign_approval_hash must return a 0x-prefixed hex string."""

    # 32-byte hash (all-zeros is valid for format tests)
    HASH_HEX = "0" * 64

    def test_returns_0x_prefixed_string(self):
        sig = sign_approval_hash(self.HASH_HEX, _TEST_PRIVATE_KEY)
        assert sig.startswith("0x"), (
            f"Expected 0x prefix, got: {sig[:6]!r}"
        )

    def test_returns_130_char_string(self):
        # 0x + 65 bytes * 2 hex chars = 0x + 130 chars = 132 total
        sig = sign_approval_hash(self.HASH_HEX, _TEST_PRIVATE_KEY)
        assert len(sig) == 132, (
            f"Expected 132 chars (0x + 130), got {len(sig)}"
        )

    def test_hex_body_is_valid(self):
        sig = sign_approval_hash(self.HASH_HEX, _TEST_PRIVATE_KEY)
        body = sig[2:]
        assert all(c in "0123456789abcdef" for c in body), (
            "Signature body is not lowercase hex"
        )

    def test_accepts_hash_without_0x_prefix(self):
        """sign_approval_hash must accept both '0x...' and bare hex."""
        hash_no_prefix = self.HASH_HEX   # no 0x
        hash_with_prefix = "0x" + self.HASH_HEX
        sig_bare = sign_approval_hash(hash_no_prefix, _TEST_PRIVATE_KEY)
        sig_prefixed = sign_approval_hash(hash_with_prefix, _TEST_PRIVATE_KEY)
        assert sig_bare == sig_prefixed, (
            "sign_approval_hash must produce identical output whether "
            "the hash has a 0x prefix or not"
        )

    def test_raises_on_wrong_length(self):
        import pytest
        with pytest.raises(ValueError, match="32 bytes"):
            sign_approval_hash("deadbeef", _TEST_PRIVATE_KEY)  # too short

    def test_raises_on_non_hex(self):
        import pytest
        with pytest.raises(ValueError):
            sign_approval_hash("g" * 64, _TEST_PRIVATE_KEY)


class TestSigningConsistency:
    """signing.py and approval_signer.py must produce identical signed bytes."""

    HASH_HEX = "9dd9761e440518dbc442e07c1d801a76113b735e3120cf6050e4bb2369ebccce"

    def test_both_modules_return_0x_prefix(self):
        """Both signing.py and approval_signer.py return 0x-prefixed strings."""
        from app.crypto import approval_signer as _signer_mod
        from unittest.mock import patch

        # Patch get_settings so approval_signer uses our test key
        class _MockSettings:
            approval_signer_private_key = _TEST_PRIVATE_KEY

        with patch("app.crypto.approval_signer.get_settings", return_value=_MockSettings()):
            sig_a = _signer_mod.sign_approval_hash(self.HASH_HEX)

        sig_b = sign_approval_hash(self.HASH_HEX, _TEST_PRIVATE_KEY)

        assert sig_a.startswith("0x"), "approval_signer result missing 0x prefix"
        assert sig_b.startswith("0x"), "signing result missing 0x prefix"

    def test_both_modules_produce_identical_bytes(self):
        """
        approval_signer.sign_approval_hash and signing.sign_approval_hash
        must produce byte-identical signatures for the same key and hash.
        This verifies the 0x normalisation did not change the signed bytes.
        """
        from app.crypto import approval_signer as _signer_mod
        from unittest.mock import patch

        class _MockSettings:
            approval_signer_private_key = _TEST_PRIVATE_KEY

        with patch("app.crypto.approval_signer.get_settings", return_value=_MockSettings()):
            sig_a = _signer_mod.sign_approval_hash(self.HASH_HEX)

        sig_b = sign_approval_hash(self.HASH_HEX, _TEST_PRIVATE_KEY)

        assert sig_a == sig_b, (
            f"Byte mismatch between approval_signer and signing:\n"
            f"  approval_signer: {sig_a}\n"
            f"  signing:         {sig_b}"
        )


class TestSigningRecovery:
    """recover_approval_signer must recover the correct signer address."""

    HASH_HEX = "9dd9761e440518dbc442e07c1d801a76113b735e3120cf6050e4bb2369ebccce"

    def test_recover_from_own_signature(self):
        sig = sign_approval_hash(self.HASH_HEX, _TEST_PRIVATE_KEY)
        recovered = recover_approval_signer(self.HASH_HEX, sig)
        assert recovered == _TEST_SIGNER_ADDRESS, (
            f"Expected {_TEST_SIGNER_ADDRESS}, recovered {recovered}"
        )

    def test_recover_accepts_signature_with_0x(self):
        sig = sign_approval_hash(self.HASH_HEX, _TEST_PRIVATE_KEY)
        assert sig.startswith("0x")
        recovered = recover_approval_signer(self.HASH_HEX, sig)
        assert recovered == _TEST_SIGNER_ADDRESS

    def test_recover_accepts_signature_without_0x(self):
        sig = sign_approval_hash(self.HASH_HEX, _TEST_PRIVATE_KEY)
        sig_no_prefix = sig[2:]  # strip 0x
        recovered = recover_approval_signer(self.HASH_HEX, sig_no_prefix)
        assert recovered == _TEST_SIGNER_ADDRESS

    def test_tampered_hash_gives_wrong_signer(self):
        """Recovering with a different hash must not return the original signer."""
        sig = sign_approval_hash(self.HASH_HEX, _TEST_PRIVATE_KEY)
        tampered_hash = "a" * 64
        recovered = recover_approval_signer(tampered_hash, sig)
        assert recovered != _TEST_SIGNER_ADDRESS

    def test_tampered_signature_gives_wrong_signer(self):
        """
        Flipping a byte in the signature must not recover the original signer.
        A tampered signature may either recover a different address OR raise
        BadSignature (if the tampered bytes produce an invalid curve point).
        Both outcomes prove the signature is not accepted as valid.
        """
        from eth_keys.exceptions import BadSignature

        sig = sign_approval_hash(self.HASH_HEX, _TEST_PRIVATE_KEY)
        # Flip first byte of the body (after 0x)
        body = sig[2:]
        flipped = format(int(body[0:2], 16) ^ 0x01, "02x") + body[2:]
        try:
            recovered = recover_approval_signer(self.HASH_HEX, "0x" + flipped)
            assert recovered != _TEST_SIGNER_ADDRESS, (
                "Tampered signature unexpectedly recovered the original signer"
            )
        except (BadSignature, ValueError):
            # A tampered signature may produce an invalid curve point — this
            # is also an acceptable proof that the signature was not accepted.
            pass


class TestSolidityCompatibilityVector:
    """
    Pins the known (hash → signature → signer) vector from
    PythonSignatureCompatibility.t.sol.

    If this test breaks, the Solidity test will also break.
    These two tests are twins — they must agree.

    Vector source: blockchain/test/PythonSignatureCompatibility.t.sol
      approvalHash    = 0x9dd9761e...
      signature       = 0x91f98369...
      expectedSigner  = 0xDBeC6b6D...
    """

    # Copied verbatim from PythonSignatureCompatibility.t.sol
    APPROVAL_HASH = "9dd9761e440518dbc442e07c1d801a76113b735e3120cf6050e4bb2369ebccce"
    KNOWN_SIGNATURE = (
        "0x"
        "91f98369a795d0f5ad85a8f15e0ed9604b1f654f2f95e7e45325ebafcdbbc518"
        "26fa4d16ebbbb569880a3e0cc8fde0fcc6e7829c06eb216801ef8bbf11ef36ae"
        "1c"
    )
    EXPECTED_SIGNER = "0xDBeC6b6D2e96687bF750Ed93C12135B445868E3A"

    def test_known_vector_recovers_expected_signer(self):
        """
        Python recover_approval_signer must recover the same address
        that Solidity's ecrecover recovers from the same inputs.
        This is the Python half of the cross-language compatibility proof.
        """
        recovered = recover_approval_signer(self.APPROVAL_HASH, self.KNOWN_SIGNATURE)
        assert recovered.lower() == self.EXPECTED_SIGNER.lower(), (
            f"Solidity compatibility vector broken!\n"
            f"  Expected:  {self.EXPECTED_SIGNER}\n"
            f"  Recovered: {recovered}\n"
            f"\nThis means Python and Solidity no longer agree on EIP-191 recovery."
        )

    def test_known_signature_is_0x_prefixed_130_chars(self):
        """The pinned vector must itself be in the normalised format."""
        assert self.KNOWN_SIGNATURE.startswith("0x")
        assert len(self.KNOWN_SIGNATURE) == 132
