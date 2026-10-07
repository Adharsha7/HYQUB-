#!/usr/bin/env bash
set -euo pipefail

# ---------------------------------------------------------------------
# HYQUB COMPLETE LOCAL ENVIRONMENT SETUP
#
# Run this after starting Anvil.
#
# It:
#   1. Confirms Anvil is running
#   2. Deploys HYQUBRegistry
#   3. Deploys EntryPoint
#   4. Deploys HYQUBWallet
#   5. Deploys TestTarget
#   6. Extracts all deployed addresses
#   7. Registers the wallet
#   8. Funds the wallet
#   9. Deposits ETH into EntryPoint
#   10. Updates backend/.env automatically
#
# ---------------------------------------------------------------------

HYQUB_ROOT="$HOME/HYQUB"

DEPLOYER_KEY="0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80"

RPC_URL="http://127.0.0.1:8545"

PYTHON="$HYQUB_ROOT/backend/venv/bin/python"

ENV_FILE="$HYQUB_ROOT/backend/.env"


# ---------------------------------------------------------------------
# Helper: Update .env
# ---------------------------------------------------------------------

update_env() {

    local KEY="$1"
    local VALUE="$2"

    if grep -q "^${KEY}=" "$ENV_FILE"; then

        sed -i "s|^${KEY}=.*|${KEY}=${VALUE}|" "$ENV_FILE"

    else

        echo "${KEY}=${VALUE}" >> "$ENV_FILE"

    fi

}


# ---------------------------------------------------------------------
# [1/5] Confirm Anvil
# ---------------------------------------------------------------------

echo
echo "=========================================="
echo "      HYQUB ENVIRONMENT SETUP"
echo "=========================================="

echo
echo "=== [1/5] Confirming Anvil is reachable ==="

BLOCK=$(curl -s -X POST "$RPC_URL" \
  -H "Content-Type: application/json" \
  --data '{
    "jsonrpc":"2.0",
    "method":"eth_blockNumber",
    "params":[],
    "id":1
  }' \
  | "$PYTHON" -c "
import sys
import json

data = json.load(sys.stdin)
print(data.get('result', 'UNREACHABLE'))
")

if [ "$BLOCK" = "UNREACHABLE" ]; then

    echo
    echo "ERROR: Anvil is not reachable."

    echo
    echo "Start Anvil first with:"

    echo
    echo "  ~/HYQUB/start_anvil.sh"

    exit 1

fi

echo "Anvil reachable."
echo "Current block: $BLOCK"


# ---------------------------------------------------------------------
# [2/5] Deploy HYQUB contracts
# ---------------------------------------------------------------------

echo
echo "=== [2/5] Deploying HYQUB contracts ==="

cd "$HYQUB_ROOT/blockchain"

forge script script/DeployHYQUB.s.sol:DeployHYQUB \
    --rpc-url "$RPC_URL" \
    --broadcast \
    --private-key "$DEPLOYER_KEY"


# ---------------------------------------------------------------------
# Extract HYQUB addresses
# ---------------------------------------------------------------------

echo
echo "Extracting HYQUB contract addresses..."

"$PYTHON" - <<PYEOF

import json

deployment_file = (
    "$HYQUB_ROOT/"
    "blockchain/"
    "broadcast/"
    "DeployHYQUB.s.sol/"
    "31337/"
    "run-latest.json"
)

with open(deployment_file, "r") as f:
    data = json.load(f)

addresses = {}

for tx in data["transactions"]:

    contract_name = tx.get("contractName")
    contract_address = tx.get("contractAddress")

    if contract_name and contract_address:

        addresses[contract_name] = contract_address


output_file = (
    "$HYQUB_ROOT/"
    "blockchain/"
    ".last_deployment.json"
)

with open(output_file, "w") as f:

    json.dump(
        addresses,
        f,
        indent=2,
    )


for name, address in addresses.items():

    print(
        f"{name} -> {address}"
    )

PYEOF


REGISTRY_ADDR=$(
"$PYTHON" -c "
import json

data = json.load(
    open('$HYQUB_ROOT/blockchain/.last_deployment.json')
)

print(data['HYQUBRegistry'])
"
)


ENTRYPOINT_ADDR=$(
"$PYTHON" -c "
import json

data = json.load(
    open('$HYQUB_ROOT/blockchain/.last_deployment.json')
)

print(data['EntryPoint'])
"
)


WALLET_ADDR=$(
"$PYTHON" -c "
import json

data = json.load(
    open('$HYQUB_ROOT/blockchain/.last_deployment.json')
)

print(data['HYQUBWallet'])
"
)


echo
echo "Registry:   $REGISTRY_ADDR"
echo "EntryPoint: $ENTRYPOINT_ADDR"
echo "Wallet:     $WALLET_ADDR"


# ---------------------------------------------------------------------
# [3/5] Deploy TestTarget
# ---------------------------------------------------------------------

echo
echo "=== [3/5] Deploying TestTarget ==="

cd "$HYQUB_ROOT/blockchain"

forge script script/DeployTestTarget.s.sol:DeployTestTarget \
    --rpc-url "$RPC_URL" \
    --broadcast \
    --private-key "$DEPLOYER_KEY"


# ---------------------------------------------------------------------
# Extract TestTarget address
# ---------------------------------------------------------------------

echo
echo "Extracting TestTarget address..."

TEST_TARGET_ADDR=$(
"$PYTHON" - <<PYEOF

import json

deployment_file = (
    "$HYQUB_ROOT/"
    "blockchain/"
    "broadcast/"
    "DeployTestTarget.s.sol/"
    "31337/"
    "run-latest.json"
)

with open(deployment_file, "r") as f:

    data = json.load(f)


for tx in data["transactions"]:

    if tx.get("contractName") == "TestTarget":

        print(
            tx["contractAddress"]
        )

        break

PYEOF
)


if [ -z "$TEST_TARGET_ADDR" ]; then

    echo
    echo "ERROR: Could not extract TestTarget address."

    exit 1

fi


echo "TestTarget: $TEST_TARGET_ADDR"


# ---------------------------------------------------------------------
# [4/5] Register wallet, fund wallet, deposit
# ---------------------------------------------------------------------

echo
echo "=== [4/5] Registering wallet and funding ==="

cd "$HYQUB_ROOT/backend"

"$PYTHON" - <<PYEOF

from web3 import Web3


RPC_URL = "$RPC_URL"

REGISTRY_ADDR = Web3.to_checksum_address(
    "$REGISTRY_ADDR"
)

ENTRYPOINT_ADDR = Web3.to_checksum_address(
    "$ENTRYPOINT_ADDR"
)

WALLET_ADDR = Web3.to_checksum_address(
    "$WALLET_ADDR"
)

DEPLOYER_KEY = "$DEPLOYER_KEY"


# -------------------------------------------------
# Connect
# -------------------------------------------------

web3 = Web3(
    Web3.HTTPProvider(RPC_URL)
)

if not web3.is_connected():

    raise RuntimeError(
        "Could not connect to Anvil"
    )


print()

print(
    "Connected to chain:",
    web3.eth.chain_id
)


account = web3.eth.account.from_key(
    DEPLOYER_KEY
)

print(
    "Deployer:",
    account.address
)


# -------------------------------------------------
# Registry ABI
# -------------------------------------------------

registry_abi = [

    {
        "inputs": [

            {
                "name": "_wallet",
                "type": "address"
            },

            {
                "name": "_keyHash",
                "type": "bytes32"
            }

        ],

        "name": "registerWallet",

        "outputs": [],

        "stateMutability": "nonpayable",

        "type": "function"

    }

]


registry = web3.eth.contract(

    address=REGISTRY_ADDR,

    abi=registry_abi

)


# -------------------------------------------------
# Register wallet
# -------------------------------------------------

print()
print("Registering wallet...")


tx = registry.functions.registerWallet(

    WALLET_ADDR,

    bytes(32)

).build_transaction({

    "from": account.address,

    "nonce": web3.eth.get_transaction_count(
        account.address
    ),

    "gas": 200000,

    "gasPrice": web3.eth.gas_price,

    "chainId": web3.eth.chain_id

})


signed = web3.eth.account.sign_transaction(

    tx,

    private_key=DEPLOYER_KEY

)


tx_hash = web3.eth.send_raw_transaction(

    signed.raw_transaction

)


receipt = web3.eth.wait_for_transaction_receipt(

    tx_hash

)


print(
    "registerWallet status:",
    receipt.status
)

print(
    "registerWallet tx:",
    tx_hash.hex()
)


if receipt.status != 1:

    raise RuntimeError(
        "Wallet registration failed"
    )


# -------------------------------------------------
# Fund wallet
# -------------------------------------------------

print()
print("Funding wallet with 2 ETH...")


fund_tx = {

    "from": account.address,

    "to": WALLET_ADDR,

    "value": web3.to_wei(
        2,
        "ether"
    ),

    "nonce": web3.eth.get_transaction_count(
        account.address
    ),

    "gas": 100000,

    "gasPrice": web3.eth.gas_price,

    "chainId": web3.eth.chain_id

}


signed_fund = web3.eth.account.sign_transaction(

    fund_tx,

    private_key=DEPLOYER_KEY

)


fund_hash = web3.eth.send_raw_transaction(

    signed_fund.raw_transaction

)


fund_receipt = (
    web3.eth.wait_for_transaction_receipt(
        fund_hash
    )
)


print(
    "fund wallet status:",
    fund_receipt.status
)


if fund_receipt.status != 1:

    raise RuntimeError(
        "Wallet funding failed"
    )


# -------------------------------------------------
# Wallet ABI
# -------------------------------------------------

wallet_abi = [

    {
        "inputs": [],

        "name": "addDeposit",

        "outputs": [],

        "stateMutability": "payable",

        "type": "function"

    }

]


wallet = web3.eth.contract(

    address=WALLET_ADDR,

    abi=wallet_abi

)


# -------------------------------------------------
# Deposit ETH
# -------------------------------------------------

print()
print("Depositing 1 ETH into EntryPoint...")


deposit_tx = wallet.functions.addDeposit().build_transaction({

    "from": account.address,

    "value": web3.to_wei(
        1,
        "ether"
    ),

    "nonce": web3.eth.get_transaction_count(
        account.address
    ),

    "gas": 100000,

    "gasPrice": web3.eth.gas_price,

    "chainId": web3.eth.chain_id

})


signed_deposit = web3.eth.account.sign_transaction(

    deposit_tx,

    private_key=DEPLOYER_KEY

)


deposit_hash = web3.eth.send_raw_transaction(

    signed_deposit.raw_transaction

)


deposit_receipt = (
    web3.eth.wait_for_transaction_receipt(
        deposit_hash
    )
)


print(
    "addDeposit status:",
    deposit_receipt.status
)


if deposit_receipt.status != 1:

    raise RuntimeError(
        "EntryPoint deposit failed"
    )


# -------------------------------------------------
# Final balance
# -------------------------------------------------

print()

print(
    "Wallet ETH balance:",
    web3.from_wei(
        web3.eth.get_balance(
            WALLET_ADDR
        ),
        "ether"
    ),
    "ETH"
)


print()
print("SETUP SUCCESSFUL")

PYEOF


# ---------------------------------------------------------------------
# [5/5] Update backend configuration
# ---------------------------------------------------------------------

echo
echo "=== [5/5] Updating backend configuration ==="


update_env \
    "HYQUB_ENTRYPOINT_ADDRESS" \
    "$ENTRYPOINT_ADDR"


update_env \
    "HYQUB_REGISTRY_ADDRESS" \
    "$REGISTRY_ADDR"


update_env \
    "HYQUB_WALLET_ADDRESS" \
    "$WALLET_ADDR"


update_env \
    "HYQUB_TEST_TARGET_ADDRESS" \
    "$TEST_TARGET_ADDR"


echo "Backend .env updated successfully."


# ---------------------------------------------------------------------
# DONE
# ---------------------------------------------------------------------

echo
echo "=========================================="
echo "       HYQUB SETUP COMPLETE 🚀"
echo "=========================================="

echo

echo "Registry:"
echo "  $REGISTRY_ADDR"

echo

echo "EntryPoint:"
echo "  $ENTRYPOINT_ADDR"

echo

echo "Wallet:"
echo "  $WALLET_ADDR"

echo

echo "TestTarget:"
echo "  $TEST_TARGET_ADDR"

echo

echo "Backend configuration updated automatically."

echo
echo "HYQUB is ready!"
echo
