from web3 import Web3

RPC_URL = "http://127.0.0.1:8545"

REGISTRY_ADDR = Web3.to_checksum_address(
    "0x5FbDB2315678afecb367f032d93F642f64180aa3"
)

ENTRYPOINT_ADDR = Web3.to_checksum_address(
    "0xe7f1725E7734CE288F8367e1Bb143E90bb3F0512"
)

WALLET_ADDR = Web3.to_checksum_address(
    "0x9fE46736679d2D9a65F0992F2272dE9f3c7fa6e0"
)

DEPLOYER_KEY = (
    "0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80"
)

web3 = Web3(Web3.HTTPProvider(RPC_URL))

if not web3.is_connected():
    raise RuntimeError("Could not connect to Anvil")

account = web3.eth.account.from_key(DEPLOYER_KEY)

print("Connected to chain:", web3.eth.chain_id)
print("Deployer:", account.address)


# Register wallet

registry_abi = [
    {
        "inputs": [
            {"name": "_wallet", "type": "address"},
            {"name": "_keyHash", "type": "bytes32"},
        ],
        "name": "registerWallet",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function",
    }
]

registry = web3.eth.contract(
    address=REGISTRY_ADDR,
    abi=registry_abi,
)

print("\nRegistering wallet...")

tx = registry.functions.registerWallet(
    WALLET_ADDR,
    bytes(32),
).build_transaction({
    "from": account.address,
    "nonce": web3.eth.get_transaction_count(account.address),
    "gas": 200000,
    "gasPrice": web3.eth.gas_price,
    "chainId": web3.eth.chain_id,
})

signed = web3.eth.account.sign_transaction(
    tx,
    private_key=DEPLOYER_KEY,
)

tx_hash = web3.eth.send_raw_transaction(
    signed.raw_transaction
)

receipt = web3.eth.wait_for_transaction_receipt(tx_hash)

print("registerWallet status:", receipt.status)
print("tx:", tx_hash.hex())

if receipt.status != 1:
    raise RuntimeError("Wallet registration failed")


# Fund wallet

print("\nFunding wallet with 2 ETH...")

fund_tx = {
    "from": account.address,
    "to": WALLET_ADDR,
    "value": web3.to_wei(2, "ether"),
    "nonce": web3.eth.get_transaction_count(account.address),
    "gas": 100000,
    "gasPrice": web3.eth.gas_price,
    "chainId": web3.eth.chain_id,
}

signed_fund = web3.eth.account.sign_transaction(
    fund_tx,
    private_key=DEPLOYER_KEY,
)

fund_hash = web3.eth.send_raw_transaction(
    signed_fund.raw_transaction
)

fund_receipt = web3.eth.wait_for_transaction_receipt(
    fund_hash
)

print("fund status:", fund_receipt.status)


# Deposit into EntryPoint

wallet_abi = [
    {
        "inputs": [],
        "name": "addDeposit",
        "outputs": [],
        "stateMutability": "payable",
        "type": "function",
    }
]

wallet = web3.eth.contract(
    address=WALLET_ADDR,
    abi=wallet_abi,
)

print("\nDepositing 1 ETH into EntryPoint...")

deposit_tx = wallet.functions.addDeposit().build_transaction({
    "from": account.address,
    "value": web3.to_wei(1, "ether"),
    "nonce": web3.eth.get_transaction_count(account.address),
    "gas": 100000,
    "gasPrice": web3.eth.gas_price,
    "chainId": web3.eth.chain_id,
})

signed_deposit = web3.eth.account.sign_transaction(
    deposit_tx,
    private_key=DEPLOYER_KEY,
)

deposit_hash = web3.eth.send_raw_transaction(
    signed_deposit.raw_transaction
)

deposit_receipt = web3.eth.wait_for_transaction_receipt(
    deposit_hash
)

print("addDeposit status:", deposit_receipt.status)


print("\n==============================")
print("HYQUB SETUP COMPLETE")
print("==============================")

print("Registry:", REGISTRY_ADDR)
print("EntryPoint:", ENTRYPOINT_ADDR)
print("Wallet:", WALLET_ADDR)
print(
    "Wallet balance:",
    web3.from_wei(
        web3.eth.get_balance(WALLET_ADDR),
        "ether"
    ),
    "ETH"
)
