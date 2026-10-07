from web3 import Web3

from app.config import get_settings
from app.utils.blockchain import get_registry_contract


def test_contract_state():

    settings = get_settings()

    contract = get_registry_contract()

    wallet = Web3.to_checksum_address(
        settings.wallet_address
    )

    print("\n==========================================")
    print("HYQUB REGISTRY STATE TEST")
    print("==========================================")

    print(
        f"\nWallet: {wallet}"
    )

    # --------------------------------------------------------
    # Check registration
    # --------------------------------------------------------

    registered = contract.functions.isRegistered(
        wallet
    ).call()

    print(
        f"Registered: {registered}"
    )

    assert registered is True, (
        f"Wallet {wallet} is not registered on-chain."
    )

    # --------------------------------------------------------
    # Read key hash
    # --------------------------------------------------------

    key_hash = contract.functions.getKeyHash(
        wallet
    ).call()

    print(
        f"Key hash: {key_hash.hex()}"
    )

    # --------------------------------------------------------
    # Read key version
    # --------------------------------------------------------

    key_version = contract.functions.getKeyVersion(
        wallet
    ).call()

    print(
        f"Key version: {key_version}"
    )

    assert key_version >= 1

    # --------------------------------------------------------
    # Final result
    # --------------------------------------------------------

    print(
        "\nHYQUB Registry state: PASSED"
    )

    print(
        "=========================================="
    )
