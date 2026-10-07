"""
HYQUB — Full End-to-End Pipeline Integration Test

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

Requires: live Anvil at http://127.0.0.1:8545
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
# ABI loading
# ---------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parents[3]

WALLET_ARTIFACT = (
    PROJECT_ROOT / "blockchain" / "out" / "HYQUBWallet.sol" / "HYQUBWallet.json"
)
ENTRYPOINT_ARTIFACT = (
    PROJECT_ROOT / "blockchain" / "out" / "EntryPoint.sol" / "EntryPoint.json"
)
TARGET_ARTIFACT = (
    PROJECT_ROOT / "blockchain" / "out" / "TestTarget.sol" / "TestTarget.json"
)


def _load_abi(path: Path) -> list:
    import json
    if not path.exists():
        raise FileNotFoundError(f"Foundry artifact not found: {path}")
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)["abi"]


def _get_web3(rpc_url: str) -> Web3:
    web3 = Web3(Web3.HTTPProvider(rpc_url))
    if not web3.is_connected():
        raise RuntimeError(f"Could not connect to Anvil at {rpc_url}")
    return web3


# ---------------------------------------------------------------------------
# Test
# ---------------------------------------------------------------------------

@pytest.mark.integration
def test_full_pipeline() -> None:
    """
    Complete HYQUB ML-DSA → quorum → ApprovalToken →
    ERC-4337 → TestTarget execution test.

    Requires live Anvil at http://127.0.0.1:8545.
    """
    settings = get_settings()

    WALLET_ADDR = Web3.to_checksum_address(settings.wallet_address)
    ENTRYPOINT_ADDR = Web3.to_checksum_address(settings.entrypoint_address)
    TARGET_ADDR = Web3.to_checksum_address(settings.test_target_address)

    WALLET_ABI = _load_abi(WALLET_ARTIFACT)
    ENTRYPOINT_ABI = _load_abi(ENTRYPOINT_ARTIFACT)
    TARGET_ABI = _load_abi(TARGET_ARTIFACT)

    # -----------------------------------------------------------------------
    # 0. Connect to Anvil
    # -----------------------------------------------------------------------
    web3 = _get_web3(settings.rpc_url)
    chain_id = web3.eth.chain_id

    print(f"\nChain ID: {chain_id}")
    print(f"Wallet: {WALLET_ADDR}")

    # -----------------------------------------------------------------------
    # 1. Read target value
    # -----------------------------------------------------------------------
    target = web3.eth.contract(address=TARGET_ADDR, abi=TARGET_ABI)
    before_value = int(target.functions.value().call())
    new_value = before_value + 1

    print(f"Target value BEFORE: {before_value}")
    print(f"Target value EXPECTED: {new_value}")

    # -----------------------------------------------------------------------
    # 2. Build calldata
    # -----------------------------------------------------------------------
    call_data = target.functions.setValue(new_value).build_transaction(
        {"from": WALLET_ADDR}
    )["data"]
    data_bytes = bytes.fromhex(call_data[2:])

    # -----------------------------------------------------------------------
    # 3. Get current on-chain key version
    # -----------------------------------------------------------------------
    import json
    REGISTRY_ARTIFACT = (
        PROJECT_ROOT / "blockchain" / "out" / "HYQUBRegistry.sol" / "HYQUBRegistry.json"
    )
    REGISTRY_ABI = _load_abi(REGISTRY_ARTIFACT)
    registry = web3.eth.contract(
        address=Web3.to_checksum_address(settings.registry_address),
        abi=REGISTRY_ABI,
    )
    key_version = int(registry.functions.getKeyVersion(WALLET_ADDR).call())
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
    print(f"message_hash: {message_hash_hex}")

    # -----------------------------------------------------------------------
    # 5. Generate ML-DSA-65 keypair
    # -----------------------------------------------------------------------
    public_key_bytes, secret_key_bytes = generate_keypair()
    public_key_encoded = encode_key_or_signature(public_key_bytes)
    print(f"Public key length: {len(public_key_bytes)}")

    # -----------------------------------------------------------------------
    # 6. Sign
    # -----------------------------------------------------------------------
    signature_bytes = sign(message_hash_hex.encode(), secret_key_bytes)
    signature_encoded = encode_key_or_signature(signature_bytes)

    # -----------------------------------------------------------------------
    # 7. Verify A + B
    # -----------------------------------------------------------------------
    verifier_a = PQVerifier(verifier_id="verifier-a")
    verifier_b = PQVerifier(verifier_id="verifier-b")

    result_a = verifier_a.verify(
        public_key=public_key_encoded,
        message=message_hash_hex,
        signature=signature_encoded,
        key_version=key_version,
    )
    result_b = verifier_b.verify(
        public_key=public_key_encoded,
        message=message_hash_hex,
        signature=signature_encoded,
        key_version=key_version,
    )

    assert result_a.verified is True
    assert result_b.verified is True

    # Tamper test
    tampered = verifier_a.verify(
        public_key=public_key_encoded,
        message=message_hash_hex,
        signature="A" + signature_encoded[1:],
        key_version=key_version,
    )
    assert tampered.verified is False

    # -----------------------------------------------------------------------
    # 8. Quorum
    # -----------------------------------------------------------------------
    quorum_result = evaluate_quorum(
        [result_a, result_b],
        required_quorum=settings.required_quorum,
    )
    assert quorum_result.approved is True
    print(f"QuorumResult: {quorum_result}")

    # -----------------------------------------------------------------------
    # 9. Approval token
    # -----------------------------------------------------------------------
    now = int(time.time())
    approval_nonce = int(time.time() * 1000)
    approval_service = ApprovalService()
    approval_token = approval_service.create_approval_token(
        wallet_address=WALLET_ADDR,
        message_hash=message_hash_hex,
        quorum_result=quorum_result,
        nonce=approval_nonce,
        issued_at=now,
        expires_at=now + 3600,
    )

    # -----------------------------------------------------------------------
    # 10. Build and submit UserOperation
    # -----------------------------------------------------------------------
    from eth_abi import encode as abi_encode

    approval_payload_bytes = canonicalize_payload(approval_token.payload)
    approval_signature_bytes = bytes.fromhex(approval_token.signature[2:])
    user_op_signature = abi_encode(
        ["bytes", "bytes"], [approval_payload_bytes, approval_signature_bytes]
    )

    wallet_contract = web3.eth.contract(address=WALLET_ADDR, abi=WALLET_ABI)
    entrypoint_contract = web3.eth.contract(address=ENTRYPOINT_ADDR, abi=ENTRYPOINT_ABI)

    ep_nonce = int(entrypoint_contract.functions.getNonce(WALLET_ADDR, 0).call())

    inner_call_data = wallet_contract.encode_abi("execute", args=[TARGET_ADDR, 0, data_bytes])

    def _pack(hi: int, lo: int) -> bytes:
        return ((hi << 128) | lo).to_bytes(32, "big")

    user_op = (
        WALLET_ADDR,
        ep_nonce,
        b"",
        inner_call_data,
        _pack(300_000, 300_000),
        50_000,
        _pack(1_000_000_000, 10_000_000_000),
        b"",
        user_op_signature,
    )

    private_key = settings.registrar_private_key
    account = web3.eth.account.from_key(private_key)

    tx = entrypoint_contract.functions.handleOps(
        [user_op], account.address
    ).build_transaction({
        "from": account.address,
        "nonce": web3.eth.get_transaction_count(account.address),
        "gas": 1_000_000,
        "gasPrice": web3.eth.gas_price,
        "chainId": chain_id,
    })
    signed = web3.eth.account.sign_transaction(tx, private_key=private_key)
    tx_hash = web3.eth.send_raw_transaction(signed.raw_transaction)
    receipt = web3.eth.wait_for_transaction_receipt(tx_hash, timeout=60)

    print(f"handleOps tx: {web3.to_hex(tx_hash)}")
    print(f"Receipt status: {receipt.status}")

    # -----------------------------------------------------------------------
    # 11. Assertions
    # -----------------------------------------------------------------------
    assert receipt.status == 1, "handleOps outer transaction failed"

    after_value = int(target.functions.value().call())
    assert after_value == new_value, (
        f"TestTarget value mismatch: expected {new_value}, got {after_value}"
    )
    print(f"TestTarget: {before_value} → {after_value} ✓")
