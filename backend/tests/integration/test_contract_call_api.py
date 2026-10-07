"""
HYQUB — Contract Call API Integration Test

Drives the full client flow through the running HTTP API:
  register → transaction-intent → sign → verify → submit-transaction

Requires: live Anvil at http://127.0.0.1:8545
          live backend at http://127.0.0.1:8000
"""

from __future__ import annotations

import pytest
import requests
from web3 import Web3

from app.config import get_settings
from app.crypto import mldsa
from app.crypto.encoding import encode_key_or_signature
from app.crypto.transaction_intent import hash_transaction_intent


BASE_URL = "http://127.0.0.1:8000"

TEST_TARGET_ABI = [
    {
        "inputs": [],
        "name": "value",
        "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}],
        "stateMutability": "view",
        "type": "function",
    },
    {
        "inputs": [{"internalType": "uint256", "name": "_value", "type": "uint256"}],
        "name": "setValue",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function",
    },
]


def _get_json(response):
    try:
        return response.json()
    except ValueError:
        return {"detail": response.text}


@pytest.mark.integration
def test_contract_call():
    """
    Full end-to-end API test: register → intent → sign → verify → submit.
    Requires live Anvil and live backend.
    """
    settings = get_settings()

    # 1. Connect to Anvil
    web3 = Web3(Web3.HTTPProvider(settings.rpc_url))
    assert web3.is_connected(), "Could not connect to Anvil"
    chain_id = web3.eth.chain_id
    assert chain_id == 31337, f"Expected chain 31337, got {chain_id}"

    wallet_address = Web3.to_checksum_address(settings.wallet_address)
    target_address = Web3.to_checksum_address(settings.test_target_address)

    # 2. Read current TestTarget value
    target = web3.eth.contract(address=target_address, abi=TEST_TARGET_ABI)
    before_value = target.functions.value().call()
    new_value = before_value + 1
    print(f"\nValue BEFORE: {before_value}")

    # 3. Encode calldata
    calldata_hex = target.encode_abi("setValue", args=[new_value])
    data_bytes = bytes.fromhex(calldata_hex[2:])

    # 4. Generate ML-DSA keypair
    public_key_bytes, secret_key_bytes = mldsa.generate_keypair()
    public_key_b64 = encode_key_or_signature(public_key_bytes)

    # 5. Register wallet
    reg = requests.post(
        f"{BASE_URL}/register",
        json={"wallet_address": wallet_address, "ml_dsa_public_key": public_key_b64},
        timeout=30,
    )
    reg_body = _get_json(reg)
    assert reg.status_code in (200, 201, 409), (
        f"Registration failed: {reg.status_code} {reg_body}"
    )
    if reg.status_code == 409:
        probe = requests.get(
            f"{BASE_URL}/transaction-intent",
            params={"wallet_address": wallet_address, "target": target_address,
                    "value_wei": 0, "data": "0x"},
            timeout=10,
        )
        key_version = _get_json(probe).get("key_version")
    else:
        key_version = reg_body["key_version"]
    print(f"Key version: {key_version}")

    # 6. Get transaction intent
    intent = requests.get(
        f"{BASE_URL}/transaction-intent",
        params={
            "wallet_address": wallet_address,
            "target": target_address,
            "value_wei": 0,
            "data": calldata_hex,
        },
        timeout=30,
    )
    intent_body = _get_json(intent)
    assert intent.status_code == 200, f"Intent failed: {intent.status_code} {intent_body}"
    message_hash_hex = intent_body["message_hash"]
    assert intent_body["chain_id"] == chain_id
    assert intent_body["key_version"] == key_version

    # 7. Verify hash independently
    calculated_hash = hash_transaction_intent(
        chain_id=chain_id,
        wallet_address=wallet_address,
        target=target_address,
        value=0,
        data=data_bytes,
        key_version=key_version,
    )
    assert calculated_hash == message_hash_hex, "Hash mismatch"

    # 8. Sign with ML-DSA
    signature_bytes = mldsa.sign(message_hash_hex.encode(), secret_key_bytes)
    signature_b64 = encode_key_or_signature(signature_bytes)

    # 9. Verify via API
    verify = requests.post(
        f"{BASE_URL}/verify",
        json={
            "wallet_address": wallet_address,
            "message": message_hash_hex,
            "signature": signature_b64,
        },
        timeout=30,
    )
    verify_body = _get_json(verify)
    assert verify.status_code == 200
    assert verify_body.get("verified") is True, f"Verification failed: {verify_body}"

    # 10. Submit transaction
    submit = requests.post(
        f"{BASE_URL}/submit-transaction",
        json={
            "wallet_address": wallet_address,
            "target": target_address,
            "value_wei": 0,
            "data": calldata_hex,
            "ml_dsa_signature": signature_b64,
        },
        timeout=60,
    )
    submit_body = _get_json(submit)
    assert submit.status_code == 200, f"Submit failed: {submit.status_code} {submit_body}"
    assert submit_body.get("success") is True
    tx_hash = submit_body["transaction_hash"]
    assert tx_hash

    # 11. Wait for receipt
    if not tx_hash.startswith("0x"):
        tx_hash = "0x" + tx_hash
    receipt = web3.eth.wait_for_transaction_receipt(tx_hash, timeout=60)
    assert receipt.status == 1, "Transaction reverted"
    print(f"Transaction: {tx_hash}")

    # 12. Verify on-chain state
    after_value = target.functions.value().call()
    assert after_value == new_value, (
        f"TestTarget mismatch: expected {new_value}, got {after_value}"
    )
    print(f"TestTarget: {before_value} → {after_value} ✓")
