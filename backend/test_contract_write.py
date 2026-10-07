from app.utils.blockchain import get_web3, get_registry_contract
from web3 import Web3

web3 = get_web3()
contract = get_registry_contract()

private_key = "0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80"

account = web3.eth.account.from_key(private_key)
sender = account.address

wallet = Web3.to_checksum_address(
    "0x70997970C51812dc3A010C7d01b50e0d17dc79C8"
)

key_hash = Web3.keccak(text="HYQUB-test-key")

print("Registrar:", sender)
print("Wallet:", wallet)
print("Key hash:", key_hash.hex())

transaction = contract.functions.registerWallet(
    wallet,
    key_hash
).build_transaction({
    "from": sender,
    "nonce": web3.eth.get_transaction_count(sender),
    "gas": 200000,
    "gasPrice": web3.eth.gas_price,
    "chainId": web3.eth.chain_id,
})

signed_transaction = web3.eth.account.sign_transaction(
    transaction,
    private_key=private_key,
)

tx_hash = web3.eth.send_raw_transaction(
    signed_transaction.raw_transaction
)

print("Transaction hash:", tx_hash.hex())

receipt = web3.eth.wait_for_transaction_receipt(tx_hash)

print("Transaction status:", receipt.status)
print("Block number:", receipt.blockNumber)
