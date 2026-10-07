import pytest
import requests

from web3 import Web3

from app.config import get_settings
from app.crypto import mldsa
from app.crypto.encoding import encode_key_or_signature
from app.crypto.transaction_intent import hash_transaction_intent


# ============================================================
# CONFIGURATION
# ============================================================

BASE_URL = "http://127.0.0.1:8000"

settings = get_settings()

RPC_URL = settings.rpc_url

WALLET_ADDR = settings.wallet_address

TARGET_ADDR = settings.test_target_address


# ============================================================
# TEST TARGET ABI
# ============================================================

TEST_TARGET_ABI = [
    {
        "inputs": [],
        "name": "value",
        "outputs": [
            {
                "internalType": "uint256",
                "name": "",
                "type": "uint256",
            }
        ],
        "stateMutability": "view",
        "type": "function",
    },
    {
        "inputs": [
            {
                "internalType": "uint256",
                "name": "_value",
                "type": "uint256",
            }
        ],
        "name": "setValue",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function",
    },
]


# ============================================================
# HELPER
# ============================================================

def get_json(response):
    try:
        return response.json()
    except ValueError:
        return {
            "detail": response.text
        }


# ============================================================
# END-TO-END TEST
# ============================================================

def test_contract_call():

    print("\n==========================================")
    print("HYQUB CONTRACT CALL API TEST")
    print("==========================================")


    # --------------------------------------------------------
    # 1. Connect to Anvil
    # --------------------------------------------------------

    web3 = Web3(
        Web3.HTTPProvider(RPC_URL)
    )

    connected = web3.is_connected()

    print(
        f"\nConnected to Anvil: {connected}"
    )

    assert connected, (
        "Could not connect to Anvil. "
        "Make sure Anvil is running."
    )

    chain_id = web3.eth.chain_id

    print(
        f"Chain ID: {chain_id}"
    )

    assert chain_id == 31337, (
        f"Expected chain ID 31337, got {chain_id}"
    )


    # --------------------------------------------------------
    # 2. Connect to TestTarget
    # --------------------------------------------------------

    wallet_address = Web3.to_checksum_address(
        WALLET_ADDR
    )

    target_address = Web3.to_checksum_address(
        TARGET_ADDR
    )

    target = web3.eth.contract(
        address=target_address,
        abi=TEST_TARGET_ABI,
    )

    before_value = target.functions.value().call()

    print(
        f"\nWallet address: {wallet_address}"
    )

    print(
        f"TestTarget address: {target_address}"
    )

    print(
        f"Value BEFORE: {before_value}"
    )


    # --------------------------------------------------------
    # 3. Create contract calldata
    # --------------------------------------------------------

    new_value = before_value + 1

    calldata_hex = target.encode_abi(
        "setValue",
        args=[new_value],
    )

    data_bytes = bytes.fromhex(
        calldata_hex[2:]
    )

    print(
        f"\nFunction: setValue({new_value})"
    )

    print(
        f"Encoded calldata: {calldata_hex}"
    )


    # --------------------------------------------------------
    # 4. Generate ML-DSA-65 keypair
    # --------------------------------------------------------

    print(
        "\nGenerating ML-DSA-65 keypair..."
    )

    public_key_bytes, secret_key_bytes = (
        mldsa.generate_keypair()
    )

    print(
        f"Public key length: "
        f"{len(public_key_bytes)} bytes"
    )

    print(
        f"Secret key length: "
        f"{len(secret_key_bytes)} bytes"
    )

    assert len(public_key_bytes) > 0
    assert len(secret_key_bytes) > 0

    public_key_b64 = encode_key_or_signature(
        public_key_bytes
    )


    # --------------------------------------------------------
    # 5. Register / synchronize wallet
    # --------------------------------------------------------

    print(
        "\nPOST /register ..."
    )

    register_payload = {
        "wallet_address": wallet_address,
        "ml_dsa_public_key": public_key_b64,
    }

    register_response = requests.post(
        f"{BASE_URL}/register",
        json=register_payload,
        timeout=30,
    )

    register_body = get_json(
        register_response
    )

    print(
        f"Registration status: "
        f"{register_response.status_code}"
    )

    print(
        f"Registration response: "
        f"{register_body}"
    )

    assert register_response.status_code in (
        200,
        201,
    ), (
        f"Registration failed: "
        f"{register_response.status_code} "
        f"{register_body}"
    )

    key_version = register_body.get(
        "key_version"
    )

    assert key_version is not None

    print(
        f"Key version: {key_version}"
    )


    # --------------------------------------------------------
    # 6. Get transaction intent
    # --------------------------------------------------------

    print(
        "\nGET /transaction-intent ..."
    )

    intent_response = requests.get(
        f"{BASE_URL}/transaction-intent",
        params={
            "wallet_address": wallet_address,
            "target": target_address,
            "value_wei": 0,
            "data": calldata_hex,
        },
        timeout=30,
    )

    intent_body = get_json(
        intent_response
    )

    print(
        f"Intent status: "
        f"{intent_response.status_code}"
    )

    print(
        f"Intent response: "
        f"{intent_body}"
    )

    assert intent_response.status_code == 200, (
        f"Transaction intent failed: "
        f"{intent_response.status_code} "
        f"{intent_body}"
    )

    message_hash_hex = intent_body.get(
        "message_hash"
    )

    assert message_hash_hex

    assert intent_body["chain_id"] == chain_id

    assert intent_body["key_version"] == key_version


    # --------------------------------------------------------
    # 7. Independently calculate hash
    # --------------------------------------------------------

    calculated_hash = hash_transaction_intent(
        chain_id=chain_id,
        wallet_address=wallet_address,
        target=target_address,
        value=0,
        data=data_bytes,
        key_version=key_version,
    )

    print(
        f"\nBackend hash:     {message_hash_hex}"
    )

    print(
        f"Calculated hash:  {calculated_hash}"
    )

    assert calculated_hash == message_hash_hex, (
        "Transaction intent hash mismatch."
    )


    # --------------------------------------------------------
    # 8. Sign with ML-DSA
    # --------------------------------------------------------

    print(
        "\nSigning TransactionIntent with ML-DSA-65..."
    )

    # IMPORTANT:
    #
    # mldsa.sign() expects:
    #
    #     sign(message, secret_key)
    #
    # The previous test had these arguments reversed.

    signature_bytes = mldsa.sign(
        message_hash_hex.encode(),
        secret_key_bytes,
    )

    print(
        f"Signature length: "
        f"{len(signature_bytes)} bytes"
    )

    assert len(signature_bytes) > 0

    signature_b64 = encode_key_or_signature(
        signature_bytes
    )

    print(
        "ML-DSA signature generated."
    )


    # --------------------------------------------------------
    # 9. Verify ML-DSA signature
    # --------------------------------------------------------

    print(
        "\nPOST /verify ..."
    )

    verify_payload = {
        "wallet_address": wallet_address,
        "message": message_hash_hex,
        "signature": signature_b64,
    }

    verify_response = requests.post(
        f"{BASE_URL}/verify",
        json=verify_payload,
        timeout=30,
    )

    verify_body = get_json(
        verify_response
    )

    print(
        f"Verification status: "
        f"{verify_response.status_code}"
    )

    print(
        f"Verification response: "
        f"{verify_body}"
    )

    assert verify_response.status_code == 200, (
        f"/verify failed: "
        f"{verify_response.status_code} "
        f"{verify_body}"
    )

    assert verify_body.get("verified") is True, (
        f"ML-DSA verification failed: "
        f"{verify_body}"
    )

    print(
        "ML-DSA verification: PASSED"
    )


    # --------------------------------------------------------
    # 10. Submit transaction
    # --------------------------------------------------------

    print(
        "\nPOST /submit-transaction ..."
    )

    submit_payload = {
        "wallet_address": wallet_address,
        "target": target_address,
        "value_wei": 0,
        "data": calldata_hex,
        "ml_dsa_signature": signature_b64,
    }

    submit_response = requests.post(
        f"{BASE_URL}/submit-transaction",
        json=submit_payload,
        timeout=60,
    )

    submit_body = get_json(
        submit_response
    )

    print(
        f"Submit status: "
        f"{submit_response.status_code}"
    )

    print(
        f"Submit response: "
        f"{submit_body}"
    )

    assert submit_response.status_code == 200, (
        f"Transaction submission failed: "
        f"{submit_response.status_code} "
        f"{submit_body}"
    )

    assert submit_body.get("success") is True, (
        f"Transaction was not successful: "
        f"{submit_body}"
    )

    transaction_hash = submit_body.get(
        "transaction_hash"
    )

    assert transaction_hash


    # --------------------------------------------------------
    # 11. Wait for receipt
    # --------------------------------------------------------

    print(
        "\nWaiting for transaction receipt..."
    )

    tx_hash = transaction_hash

    if not tx_hash.startswith("0x"):
        tx_hash = "0x" + tx_hash

    receipt = web3.eth.wait_for_transaction_receipt(
        tx_hash,
        timeout=60,
    )

    print(
        f"Receipt status: {receipt.status}"
    )

    print(
        f"Block number: {receipt.blockNumber}"
    )

    assert receipt.status == 1, (
        "EntryPoint transaction reverted."
    )


    # --------------------------------------------------------
    # 12. Verify TestTarget state
    # --------------------------------------------------------

    after_value = target.functions.value().call()

    print(
        f"\nValue AFTER: {after_value}"
    )

    print(
        f"Expected value: {new_value}"
    )

    assert after_value == new_value, (
        f"TestTarget state mismatch. "
        f"Expected {new_value}, got {after_value}."
    )


    # --------------------------------------------------------
    # 13. SUCCESS
    # --------------------------------------------------------

    print(
        "\n=========================================="
    )

    print(
        "HYQUB CONTRACT CALL TEST PASSED"
    )

    print(
        "=========================================="
    )

    print(
        f"TestTarget: {before_value} -> {after_value}"
    )

    print(
        f"Transaction: {tx_hash}"
    )

    print(
        "ML-DSA signing: PASSED"
    )

    print(
        "ML-DSA verification: PASSED"
    )

    print(
        "Transaction submission: PASSED"
    )

    print(
        "HYQUBWallet execution: PASSED"
    )

    print(
        "TestTarget.setValue(): PASSED"
    )

    print(
        "On-chain state verification: PASSED"
    )

    print(
        "=========================================="
    )
