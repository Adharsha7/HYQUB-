import json
import time
from pathlib import Path

from web3 import Web3

from app.crypto import mldsa
from app.crypto.encoding import encode_key_or_signature
from app.crypto.transaction_intent import hash_transaction_intent
from app.crypto.approval import canonicalize_payload
from app.services.verifier_engine import PQVerifier
from app.services.quorum_engine import evaluate_quorum
from app.services.approval_service import ApprovalService

RPC_URL = "http://127.0.0.1:8545"
WALLET_ADDR = Web3.to_checksum_address("0x9fE46736679d2D9a65F0992F2272dE9f3c7fa6e0")
ENTRYPOINT_ADDR = Web3.to_checksum_address("0xe7f1725E7734CE288F8367e1Bb143E90bb3F0512")
REGISTRY_ADDR = Web3.to_checksum_address("0x5FbDB2315678afecb367f032d93F642f64180aa3")
DEPLOYER_KEY = "0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80"
TARGET_ADDR = Web3.to_checksum_address("0x4444444444444444444444444444444444444444")

web3 = Web3(Web3.HTTPProvider(RPC_URL))
account = web3.eth.account.from_key(DEPLOYER_KEY)

print("=== BASIC CHAIN STATE ===", flush=True)
print("Current block number:", web3.eth.block_number, flush=True)
print("Wallet code size:", len(web3.eth.get_code(WALLET_ADDR)), flush=True)
print("EntryPoint code size:", len(web3.eth.get_code(ENTRYPOINT_ADDR)), flush=True)
print("Registry code size:", len(web3.eth.get_code(REGISTRY_ADDR)), flush=True)
print("Wallet ETH balance:", web3.eth.get_balance(WALLET_ADDR), flush=True)


def load_abi(name: str) -> list:
    path = Path("../blockchain/out") / f"{name}.sol" / f"{name}.json"
    with open(path) as f:
        return json.load(f)["abi"]


wallet_abi = load_abi("HYQUBWallet")
entrypoint_abi = load_abi("EntryPoint")
registry_abi = load_abi("HYQUBRegistry")

wallet_contract = web3.eth.contract(address=WALLET_ADDR, abi=wallet_abi)
entrypoint_contract = web3.eth.contract(address=ENTRYPOINT_ADDR, abi=entrypoint_abi)
registry_contract = web3.eth.contract(address=REGISTRY_ADDR, abi=registry_abi)

print("Wallet's configured registry:", wallet_contract.functions.registry().call(), flush=True)
print("Wallet's configured approvalSigner:", wallet_contract.functions.approvalSigner().call(), flush=True)
print("Wallet's configured entryPoint:", wallet_contract.functions.entryPoint().call(), flush=True)
print("Wallet's EntryPoint deposit:", wallet_contract.functions.getDeposit().call(), flush=True)
print("Registry isRegistered(wallet):", registry_contract.functions.isRegistered(WALLET_ADDR).call(), flush=True)
print("Registry getKeyVersion(wallet):", registry_contract.functions.getKeyVersion(WALLET_ADDR).call(), flush=True)

current_key_version = registry_contract.functions.getKeyVersion(WALLET_ADDR).call()
value = web3.to_wei(0.01, "ether")
data = b""

print(flush=True)
print("=== REBUILDING AND RESUBMITTING WITH A FRESH NONCE ===", flush=True)

message_hash_hex = hash_transaction_intent(
    chain_id=web3.eth.chain_id,
    wallet_address=WALLET_ADDR,
    target=TARGET_ADDR,
    value=value,
    data=data,
    key_version=current_key_version,
)
print("message_hash:", message_hash_hex, flush=True)

public_key_bytes, secret_key_bytes = mldsa.generate_keypair()
message_bytes = message_hash_hex.encode("utf-8")
mldsa_signature_bytes = mldsa.sign(message_bytes, secret_key_bytes)
public_key_b64 = encode_key_or_signature(public_key_bytes)
mldsa_signature_b64 = encode_key_or_signature(mldsa_signature_bytes)

verifier_a = PQVerifier(verifier_id="verifier-a")
verifier_b = PQVerifier(verifier_id="verifier-b")
result_a = verifier_a.verify(public_key=public_key_b64, message=message_hash_hex, signature=mldsa_signature_b64, key_version=current_key_version)
result_b = verifier_b.verify(public_key=public_key_b64, message=message_hash_hex, signature=mldsa_signature_b64, key_version=current_key_version)
quorum_result = evaluate_quorum([result_a, result_b], required_quorum=2)
assert quorum_result.approved

now = int(time.time())
approval_service = ApprovalService()
# Use a nonce well above anything used so far in this session.
fresh_nonce = 1000 + int(time.time()) % 100000
approval_token = approval_service.create_approval_token(
    wallet_address=WALLET_ADDR,
    message_hash=message_hash_hex,
    quorum_result=quorum_result,
    nonce=fresh_nonce,
    issued_at=now,
    expires_at=now + 3600,
)
print("Using approval nonce:", fresh_nonce, flush=True)

approval_payload_bytes = canonicalize_payload(approval_token.payload)
approval_signature_bytes = bytes.fromhex(approval_token.signature[2:])

from eth_abi import encode as abi_encode
user_op_signature = abi_encode(["bytes", "bytes"], [approval_payload_bytes, approval_signature_bytes])

call_data = wallet_contract.encode_abi("execute", args=[TARGET_ADDR, value, data])


def pack_gas_limits(hi: int, lo: int) -> bytes:
    return (hi << 128 | lo).to_bytes(32, "big")


user_op = (
    WALLET_ADDR,
    0,
    b"",
    call_data,
    pack_gas_limits(300_000, 150_000),
    50_000,
    pack_gas_limits(1_000_000_000, 10_000_000_000),
    b"",
    user_op_signature,
)

target_balance_before = web3.eth.get_balance(TARGET_ADDR)
print("Target balance before:", target_balance_before, flush=True)

tx = entrypoint_contract.functions.handleOps([user_op], account.address).build_transaction({
    "from": account.address,
    "nonce": web3.eth.get_transaction_count(account.address),
    "gas": 1_000_000,
    "gasPrice": web3.eth.gas_price,
    "chainId": web3.eth.chain_id,
})
signed = web3.eth.account.sign_transaction(tx, private_key=DEPLOYER_KEY)
tx_hash = web3.eth.send_raw_transaction(signed.raw_transaction)
receipt = web3.eth.wait_for_transaction_receipt(tx_hash)

print("handleOps status:", receipt.status, flush=True)
print("Target balance after:", web3.eth.get_balance(TARGET_ADDR), flush=True)

print(flush=True)
print("=== DECODING ALL EVENT LOGS FROM THE RECEIPT ===", flush=True)
for log in receipt.logs:
    try:
        event = entrypoint_contract.events.UserOperationEvent().process_log(log)
        print("UserOperationEvent:", dict(event["args"]), flush=True)
        continue
    except Exception:
        pass
    try:
        event = entrypoint_contract.events.UserOperationRevertReason().process_log(log)
        args = dict(event["args"])
        revert_reason_bytes = args.get("revertReason", b"")
        print("UserOperationRevertReason raw bytes:", revert_reason_bytes.hex(), flush=True)
        # Try to decode as a standard Error(string) revert
        if len(revert_reason_bytes) >= 4 and revert_reason_bytes[:4] == bytes.fromhex("08c379a0"):
            from eth_abi import decode as abi_decode
            decoded = abi_decode(["string"], revert_reason_bytes[4:])
            print("Decoded revert string:", decoded[0], flush=True)
        continue
    except Exception:
        pass
    print("Unrecognized log:", log, flush=True)

