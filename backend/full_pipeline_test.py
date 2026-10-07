"""
HYQUB — Full End-to-End Pipeline Test

Pipeline:

    TestTarget transaction
        ↓
    TransactionIntent hash
        ↓
    ML-DSA-65 key generation
        ↓
    ML-DSA signature
        ↓
    Verifier A
        ↓
    Verifier B
        ↓
    2-of-2 quorum
        ↓
    ECDSA Approval Token
        ↓
    ERC-4337 UserOperation
        ↓
    HYQUBWallet.validateUserOp()
        ↓
    EntryPoint.handleOps()
        ↓
    TestTarget.setValue()

Important:
- UserOperation nonce is READ FROM the deployed EntryPoint.
- It must never be hardcoded to 0 because the EntryPoint nonce changes
  after every successful UserOperation.
"""

from __future__ import annotations

import time
from pathlib import Path

import pytest
from web3 import Web3

from app.config import get_settings
from app.crypto.approval import canonicalize_payload
from app.crypto.encoding import encode_key_or_signature
from app.crypto.mldsa import generate_keypair, sign
from app.crypto.transaction_intent import hash_transaction_intent
from app.services.approval_service import ApprovalService
from app.services.quorum_engine import evaluate_quorum
from app.services.verifier_engine import PQVerifier


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

settings = get_settings()

RPC_URL = settings.rpc_url

WALLET_ADDR = Web3.to_checksum_address(
    settings.wallet_address
)

ENTRYPOINT_ADDR = Web3.to_checksum_address(
    settings.entrypoint_address
)

TARGET_ADDR = Web3.to_checksum_address(
    settings.test_target_address
)


# ---------------------------------------------------------------------------
# ABI loading
# ---------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parents[1]

WALLET_ARTIFACT = (
    PROJECT_ROOT
    / "blockchain"
    / "out"
    / "HYQUBWallet.sol"
    / "HYQUBWallet.json"
)

ENTRYPOINT_ARTIFACT = (
    PROJECT_ROOT
    / "blockchain"
    / "out"
    / "EntryPoint.sol"
    / "EntryPoint.json"
)

TARGET_ARTIFACT = (
    PROJECT_ROOT
    / "blockchain"
    / "out"
    / "TestTarget.sol"
    / "TestTarget.json"
)


def load_abi(path: Path) -> list:
    """
    Load an ABI from a Foundry artifact.
    """
    import json

    if not path.exists():
        raise FileNotFoundError(
            f"Foundry artifact not found:\n{path}"
        )

    with path.open("r", encoding="utf-8") as f:
        artifact = json.load(f)

    return artifact["abi"]


WALLET_ABI = load_abi(WALLET_ARTIFACT)
ENTRYPOINT_ABI = load_abi(ENTRYPOINT_ARTIFACT)
TARGET_ABI = load_abi(TARGET_ARTIFACT)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def get_web3() -> Web3:
    """
    Create a Web3 connection to Anvil.
    """
    web3 = Web3(
        Web3.HTTPProvider(RPC_URL)
    )

    if not web3.is_connected():
        raise RuntimeError(
            f"Could not connect to Anvil at {RPC_URL}"
        )

    return web3


def get_entrypoint_nonce(web3: Web3) -> int:
    """
    Read the CURRENT ERC-4337 nonce from EntryPoint.

    EntryPoint maintains the nonce used by PackedUserOperation.
    This is separate from HYQUBWallet.nonce().
    """

    entrypoint = web3.eth.contract(
        address=ENTRYPOINT_ADDR,
        abi=ENTRYPOINT_ABI,
    )

    nonce = entrypoint.functions.getNonce(
        WALLET_ADDR,
        0,
    ).call()

    return int(nonce)



# ---------------------------------------------------------------------------
# Main test
# ---------------------------------------------------------------------------

def test_full_pipeline() -> None:
    """
    Complete HYQUB ML-DSA → quorum → ApprovalToken →
    ERC-4337 → TestTarget execution test.
    """

    # -----------------------------------------------------------------------
    # 0. Connect to Anvil
    # -----------------------------------------------------------------------

    web3 = get_web3()

    chain_id = web3.eth.chain_id

    print()
    print("=" * 78)
    print("HYQUB FULL END-TO-END PIPELINE")
    print("=" * 78)

    print()
    print(f"Connected to Anvil: {web3.is_connected()}")
    print(f"RPC URL: {RPC_URL}")
    print(f"Chain ID: {chain_id}")
    print(f"Wallet address: {WALLET_ADDR}")
    print(f"EntryPoint address: {ENTRYPOINT_ADDR}")
    print(f"Target address: {TARGET_ADDR}")

    # -----------------------------------------------------------------------
    # 1. Read target value
    # -----------------------------------------------------------------------

    target = web3.eth.contract(
        address=TARGET_ADDR,
        abi=TARGET_ABI,
    )

    before_value = int(
        target.functions.value().call()
    )

    new_value = before_value + 1

    print()
    print(f"Target value BEFORE:   {before_value}")
    print(f"Target value EXPECTED: {new_value}")

    # -----------------------------------------------------------------------
    # 2. Build target calldata
    # -----------------------------------------------------------------------

    call_data = target.functions.setValue(
        new_value
    ).build_transaction(
        {
            "from": WALLET_ADDR,
        }
    )["data"]

    print()
    print("Function: setValue(%d)" % new_value)
    print(f"Calldata: {call_data}")

    data_bytes = bytes.fromhex(
        call_data[2:]
    )

    # -----------------------------------------------------------------------
    # 3. Get current on-chain wallet key version
    # -----------------------------------------------------------------------

    wallet = web3.eth.contract(
        address=WALLET_ADDR,
        abi=WALLET_ABI,
    )

    registry_address = Web3.to_checksum_address(
        settings.registry_address
    )

    registry_artifact = (
        PROJECT_ROOT
        / "blockchain"
        / "out"
        / "HYQUBRegistry.sol"
        / "HYQUBRegistry.json"
    )

    REGISTRY_ABI = load_abi(
        registry_artifact
    )

    registry = web3.eth.contract(
        address=registry_address,
        abi=REGISTRY_ABI,
    )

    key_version = int(
        registry.functions.getKeyVersion(
            WALLET_ADDR
        ).call()
    )

    print()
    print(f"Current ML-DSA key version: {key_version}")

    # -----------------------------------------------------------------------
    # 4. Create TransactionIntent hash
    # -----------------------------------------------------------------------

    message_hash_hex = hash_transaction_intent(
        chain_id=chain_id,
        wallet_address=WALLET_ADDR,
        target=TARGET_ADDR,
        value=0,
        data=data_bytes,
        key_version=key_version,
    )

    print()
    print("[1] TransactionIntent")
    print(f"    message_hash: {message_hash_hex}")

    # -----------------------------------------------------------------------
    # 5. Generate ML-DSA-65 keypair
    # -----------------------------------------------------------------------

    print()
    print("[2] Generating ML-DSA-65 keypair...")

    public_key_bytes, secret_key_bytes = (
        generate_keypair()
    )

    public_key_encoded = encode_key_or_signature(
        public_key_bytes
    )

    print(
        f"    Public key length: "
        f"{len(public_key_bytes)}"
    )

    print(
        f"    Secret key length: "
        f"{len(secret_key_bytes)}"
    )

    # -----------------------------------------------------------------------
    # 6. Sign TransactionIntent
    # -----------------------------------------------------------------------

    signature_bytes = sign(
        message_hash_hex.encode(),
        secret_key_bytes,
    )

    signature_encoded = encode_key_or_signature(
        signature_bytes
    )

    print(
        f"    Signature length: "
        f"{len(signature_bytes)}"
    )

    # -----------------------------------------------------------------------
    # 7. Independent verifier A
    # -----------------------------------------------------------------------

    verifier_a = PQVerifier(
        verifier_id="verifier-a"
    )

    result_a = verifier_a.verify(
        public_key=public_key_encoded,
        message=message_hash_hex,
        signature=signature_encoded,
        key_version=key_version,
    )

    print()
    print("[3] Verifier A result:")
    print(f"    {result_a}")

    assert result_a.verified is True
    assert result_a.key_version == key_version

    # -----------------------------------------------------------------------
    # 8. Independent verifier B
    # -----------------------------------------------------------------------

    verifier_b = PQVerifier(
        verifier_id="verifier-b"
    )

    result_b = verifier_b.verify(
        public_key=public_key_encoded,
        message=message_hash_hex,
        signature=signature_encoded,
        key_version=key_version,
    )

    print()
    print("[3] Verifier B result:")
    print(f"    {result_b}")

    assert result_b.verified is True
    assert result_b.key_version == key_version

    # -----------------------------------------------------------------------
    # 9. Tamper test
    # -----------------------------------------------------------------------

    tampered_signature = (
        "A" + signature_encoded[1:]
    )

    tampered_result = verifier_a.verify(
        public_key=public_key_encoded,
        message=message_hash_hex,
        signature=tampered_signature,
        key_version=key_version,
    )

    print()
    print("[3] Tampered signature result:")
    print(f"    {tampered_result}")

    assert tampered_result.verified is False

    # -----------------------------------------------------------------------
    # 10. Quorum
    # -----------------------------------------------------------------------

    quorum_result = evaluate_quorum(
        [
            result_a,
            result_b,
        ],
        required_quorum=settings.required_quorum,
    )

    print()
    print("[4] QuorumResult:")
    print(f"    {quorum_result}")

    assert quorum_result.approved is True
    assert len(
        quorum_result.approving_verifier_ids
    ) >= settings.required_quorum

    assert (
        quorum_result.key_version
        == key_version
    )

    # -----------------------------------------------------------------------
    # 11. Create Approval Token
    # -----------------------------------------------------------------------

    approval_service = ApprovalService()

    approval_nonce = int(
        time.time() * 1000
    )

    issued_at = int(
        time.time()
    )

    expires_at = issued_at + 3600

    approval_token = (
        approval_service.create_approval_token(
            wallet_address=WALLET_ADDR,
            message_hash=message_hash_hex,
            quorum_result=quorum_result,
            nonce=approval_nonce,
            issued_at=issued_at,
            expires_at=expires_at,
        )
    )

    print()
    print("[5] ApprovalToken created.")

    # -----------------------------------------------------------------------
    # 12. Structural ApprovalToken validation
    # -----------------------------------------------------------------------

    approval_payload = (
        approval_token.payload
    )

    approval_signature = (
        approval_token.signature
    )

    canonical_payload = canonicalize_payload(
        approval_payload
    )

    assert canonical_payload is not None

    print(
        f"    Approval nonce: {approval_nonce}"
    )

    print(
        f"    Issued at: {issued_at}"
    )

    print(
        f"    Expires at: {expires_at}"
    )

    print(
        "    Structural self-check: True"
    )

    # -----------------------------------------------------------------------
    # 13. Encode ApprovalToken into UserOp signature
    # -----------------------------------------------------------------------

    approval_payload_bytes = (
        canonical_payload
    )

    approval_signature_bytes = (
        approval_signature
    )

    user_op_signature = web3.codec.encode(
        [
            "bytes",
            "bytes",
        ],
        [
            approval_payload_bytes,
            approval_signature_bytes,
        ],
    )

    # -----------------------------------------------------------------------
    # 14. CRITICAL FIX:
    #     Read current wallet nonce from chain
    # -----------------------------------------------------------------------

    current_wallet_nonce = (
        get_entrypoint_nonce(web3)
    )

    print()
    print(
        "[6] Wallet nonce BEFORE: "
        f"{current_wallet_nonce}"
    )

    # -----------------------------------------------------------------------
    # 15. Build HYQUBWallet execute calldata
    # -----------------------------------------------------------------------

    execute_call_data = (
        wallet.functions.execute(
            TARGET_ADDR,
            0,
            data_bytes,
        )._encode_transaction_data()
    )

    print()
    print(
        "[6] HYQUBWallet execute calldata:"
    )
    print(
        f"    {execute_call_data}"
    )

    # -----------------------------------------------------------------------
    # 16. Build PackedUserOperation
    # -----------------------------------------------------------------------

    #
    # ERC-4337 PackedUserOperation fields:
    #
    # sender
    # nonce
    # initCode
    # callData
    # accountGasLimits
    # preVerificationGas
    # gasFees
    # paymasterAndData
    # signature
    #

    call_gas_limit = 300000
    verification_gas_limit = 300000
    pre_verification_gas = 50000

    max_priority_fee_per_gas = web3.to_wei(
        1,
        "gwei",
    )

    max_fee_per_gas = web3.to_wei(
        10,
        "gwei",
    )

    # Packed accountGasLimits:
    #
    # verificationGasLimit = first 16 bytes
    # callGasLimit         = second 16 bytes
    #

    account_gas_limits = (
        verification_gas_limit.to_bytes(
            16,
            "big",
        )
        + call_gas_limit.to_bytes(
            16,
            "big",
        )
    )

    # Packed gasFees:
    #
    # maxPriorityFeePerGas = first 16 bytes
    # maxFeePerGas         = second 16 bytes
    #

    gas_fees = (
        max_priority_fee_per_gas.to_bytes(
            16,
            "big",
        )
        + max_fee_per_gas.to_bytes(
            16,
            "big",
        )
    )

    user_op = (
        WALLET_ADDR,
        current_wallet_nonce,
        b"",
        bytes.fromhex(
            execute_call_data[2:]
        ),
        account_gas_limits,
        pre_verification_gas,
        gas_fees,
        b"",
        user_op_signature,
    )

    # -----------------------------------------------------------------------
    # 17. Submit UserOperation through EntryPoint
    # -----------------------------------------------------------------------

    entrypoint = web3.eth.contract(
        address=ENTRYPOINT_ADDR,
        abi=ENTRYPOINT_ABI,
    )

    print()
    print(
        "[6] Submitting UserOperation..."
    )

    transaction = (
        entrypoint.functions.handleOps(
            [user_op],
            Web3.to_checksum_address(
                web3.eth.accounts[0]
            ),
        ).build_transaction(
            {
                "from": Web3.to_checksum_address(
                    web3.eth.accounts[0]
                ),
                "nonce": web3.eth.get_transaction_count(
                    Web3.to_checksum_address(
                        web3.eth.accounts[0]
                    )
                ),
                "gas": 1000000,
                "maxFeePerGas": max_fee_per_gas,
                "maxPriorityFeePerGas": max_priority_fee_per_gas,
                "chainId": chain_id,
            }
        )
    )

    # -----------------------------------------------------------------------
    # 18. Sign outer EntryPoint transaction
    # -----------------------------------------------------------------------

    relayer_account = (
        web3.eth.account.from_key(
            settings.registrar_private_key
        )
    )

    transaction["from"] = (
        relayer_account.address
    )

    # Refresh relayer nonce after setting sender
    transaction["nonce"] = (
        web3.eth.get_transaction_count(
            relayer_account.address
        )
    )

    signed_transaction = (
        relayer_account.sign_transaction(
            transaction
        )
    )

    tx_hash = web3.eth.send_raw_transaction(
        signed_transaction.raw_transaction
    )

    print(
        f"[6] Transaction hash: "
        f"{tx_hash.hex()}"
    )

    # -----------------------------------------------------------------------
    # 19. Wait for receipt
    # -----------------------------------------------------------------------

    receipt = web3.eth.wait_for_transaction_receipt(
        tx_hash
    )

    print(
        f"[6] handleOps receipt status: "
        f"{receipt.status}"
    )

    if receipt.status != 1:
        pytest.fail(
            "EntryPoint handleOps transaction "
            "reverted."
        )

    # -----------------------------------------------------------------------
    # 20. Read target value after execution
    # -----------------------------------------------------------------------

    after_value = int(
        target.functions.value().call()
    )

    print()
    print(
        f"Target value AFTER:    {after_value}"
    )

    print(
        f"Target value EXPECTED: {new_value}"
    )

    # -----------------------------------------------------------------------
    # 21. Assertions
    # -----------------------------------------------------------------------

    assert after_value == new_value

    # EntryPoint nonce should increment by exactly one
    nonce_after = get_entrypoint_nonce(web3)

    print()
    print(
        f"EntryPoint nonce AFTER: {nonce_after}"
    )

    assert nonce_after == (
        current_wallet_nonce + 1
    )

    print()
    print("=" * 78)
    print("HYQUB FULL PIPELINE PASSED")
    print("=" * 78)
    print()
