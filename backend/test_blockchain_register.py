from app.utils.blockchain import register_wallet_on_chain
from eth_account import Account

# Generate a fresh wallet address each run so re-running this script
# doesn't hit "Already registered" on a long-lived local chain.
wallet = Account.create().address

# SHA-256 hash of a fake/test ML-DSA public key
key_hash = (
    "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
    "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
)

tx_hash = register_wallet_on_chain(
    wallet_address=wallet,
    key_hash=key_hash,
)

print("Wallet:", wallet)
print("Transaction hash:", tx_hash)
