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
# HELPERS
# ============================================================

def get_json(response):
    try:
        return response.json()
    except ValueError:
        return {
            "detail": response.text
        }


# ============================================================
# TEST
# ============================================================

def test_submit_transaction():

    print("\n==========================================")
    print("HYQUB SUBMIT TRANSACTION API TEST")
    print("==========================================")


    # --------------------------------------------------------
    # 1. Connect to Anvil
    # --------------------------------------------------------

    web3 = Web3(
        Web3.HTTPProvider(RPC_URL)
    )

    assert web3.is_connected(), (
        "Could not connect to Anvil."
    )

    chain_id = web3.eth.chain_id

    print(
        f"\nChain ID: {chain_id}"
    )

    assert chain_id == 31337


    # --------------------------------------------------------
    # 2. Addresses
    # --------------------------------------------------------

    wallet_address = Web3.to_checksum_address(
        WALLET_ADDR
    )

    target_address = Web3.to_checksum_address(
        TARGET_ADDR
    )

    print(
        f"Wallet: {wallet_address}"
    )

    print(
        f"Target: {target_address}"
    )


    # --------------------------------------------------------
    # 3. Connect to TestTarget
    # --------------------------------------------------------

    target = web3.eth.contract(
        address=target_address,
        abi=TEST_TARGET_ABI,
    )

    before_value = target.functions.value().call()

    new_value = before_value + 1

    print(
        f"\nValue BEFORE: {before_value}"
    )

    print(
        f"Value AFTER expected: {new_value}"
    )


    # --------------------------------------------------------
    # 4. Encode setValue()
    # --------------------------------------------------------

    calldata_hex = target.encode_abi(
        "setValue",
        args=[new_value],
    )

    data_bytes = bytes.fromhex(
        calldata_hex[2:]
    )

    print(
        f"Calldata: {calldata_hex}"
    )


    # --------------------------------------------------------
    # 5. Generate ML-DSA keypair
    # --------------------------------------------------------

    print(
        "\nGenerating ML-DSA-65 keypair..."
    )

    public_key_bytes, secret_key_bytes = (
        mldsa.generate_keypair()
    )

    public_key_b64 = encode_key_or_signature(
        public_key_bytes
    )

    print(
        f"Public key length: "
        f"{len(public_key_bytes)} bytes"
    )

    print(
        f"Secret key length: "
        f"{len(secret_key_bytes)} bytes"
    )


    # --------------------------------------------------------
    # 6. Register / synchronize wallet
    # --------------------------------------------------------

    print(
        "\nPOST /register ..."
    )

    register_response = requests.post(
        f"{BASE_URL}/register",
        json={
            "wallet_address": wallet_address,
            "ml_dsa_public_key": public_key_b64,
        },
        timeout=30,
    )

    register_body = get_json(
        register_response
    )

    print(
        f"Register status: "
        f"{register_response.status_code}"
    )

    print(
        f"Register response: "
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

    key_version = register_body["key_version"]

    print(
        f"Key version: {key_version}"
    )


    # --------------------------------------------------------
    # 7. Get transaction intent
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

    message_hash = intent_body["message_hash"]


    # --------------------------------------------------------
    # 8. Independently verify transaction hash
    # --------------------------------------------------------

    calculated_hash = hash_transaction_intent(
        chain_id=chain_id,
        wallet_address=wallet_address,
        target=target_address,
        value=0,
        data=data_bytes,
        key_version=key_version,
    )

    assert calculated_hash == message_hash, (
        "Transaction intent hash mismatch."
    )

    print(
        "\nTransaction intent hash: "
        f"{message_hash}"
    )


    # --------------------------------------------------------
    # 9. Sign intent with ML-DSA
    # --------------------------------------------------------

    print(
        "\nSigning transaction intent..."
    )

    signature_bytes = mldsa.sign(
        message_hash.encode(),
        secret_key_bytes,
    )

    signature_b64 = encode_key_or_signature(
        signature_bytes
    )

    print(
        f"Signature length: "
        f"{len(signature_bytes)} bytes"
    )


    # --------------------------------------------------------
    # 10. Verify signature
    # --------------------------------------------------------

    print(
        "\nPOST /verify ..."
    )

    verify_response = requests.post(
        f"{BASE_URL}/verify",
        json={
            "wallet_address": wallet_address,
            "message": message_hash,
            "signature": signature_b64,
        },
        timeout=30,
    )

    verify_body = get_json(
        verify_response
    )

    print(
        f"Verify status: "
        f"{verify_response.status_code}"
    )

    print(
        f"Verify response: "
        f"{verify_body}"
    )

    assert verify_response.status_code == 200

    assert verify_body.get("verified") is True, (
        f"Signature verification failed: "
        f"{verify_body}"
    )


    # --------------------------------------------------------
    # 11. Submit transaction
    # --------------------------------------------------------

    print(
        "\nPOST /submit-transaction ..."
    )

    submit_response = requests.post(
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
        f"Submit transaction failed: "
        f"{submit_response.status_code} "
        f"{submit_body}"
    )

    assert submit_body.get("success") is True, (
        f"Transaction failed: "
        f"{submit_body}"
    )

    transaction_hash = submit_body.get(
        "transaction_hash"
    )

    assert transaction_hash


    # --------------------------------------------------------
    # 12. Wait for receipt
    # --------------------------------------------------------

    tx_hash = transaction_hash

    if not tx_hash.startswith("0x"):
        tx_hash = "0x" + tx_hash

    print(
        f"\nTransaction: {tx_hash}"
    )

    receipt = web3.eth.wait_for_transaction_receipt(
        tx_hash,
        timeout=60,
    )

    print(
        f"Receipt status: {receipt.status}"
    )

    assert receipt.status == 1


    # --------------------------------------------------------
    # 13. Verify on-chain state
    # --------------------------------------------------------

    after_value = target.functions.value().call()

    print(
        f"\nValue BEFORE: {before_value}"
    )

    print(
        f"Value AFTER:  {after_value}"
    )

    assert after_value == new_value, (
        f"TestTarget value mismatch. "
        f"Expected {new_value}, got {after_value}"
    )


    # --------------------------------------------------------
    # 14. SUCCESS
    # --------------------------------------------------------

    print(
        "\n=========================================="
    )

    print(
        "HYQUB SUBMIT TRANSACTION TEST PASSED"
    )

    print(
        "=========================================="
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
        "EntryPoint transaction: PASSED"
    )

    print(
        "HYQUBWallet execution: PASSED"
    )

    print(
        "TestTarget state update: PASSED"
    )

    print(
        "=========================================="
    )
