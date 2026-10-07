from app.utils.blockchain import get_web3, get_registry_contract

web3 = get_web3()

print("Connected:", web3.is_connected())
print("Chain ID:", web3.eth.chain_id)

contract = get_registry_contract()

print("Contract:", contract.address)

