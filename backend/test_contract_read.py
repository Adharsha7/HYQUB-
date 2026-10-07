from app.utils.blockchain import get_registry_contract
from web3 import Web3

contract = get_registry_contract()

wallet = Web3.to_checksum_address(
        "0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266"
)

registered = contract.functions.isRegistered(wallet).call()

print("Wallet:", wallet)
print("Registered:", registered)

