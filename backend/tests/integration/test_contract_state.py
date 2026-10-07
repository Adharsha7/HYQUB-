"""
HYQUB — Registry Contract State Integration Test

Verifies the on-chain HYQUBRegistry state for the configured wallet.

Requires: live Anvil at http://127.0.0.1:8545
"""

from __future__ import annotations

import pytest
from web3 import Web3

from app.config import get_settings
from app.utils.blockchain import get_web3, get_registry_contract


@pytest.mark.integration
def test_contract_state():
    """
    Check that the configured wallet is registered on-chain and
    has a valid key version.
    """
    settings = get_settings()
    wallet = Web3.to_checksum_address(settings.wallet_address)

    web3 = get_web3()
    contract = get_registry_contract(web3)

    print(f"\nWallet: {wallet}")

    # Check registration
    registered = contract.functions.isRegistered(wallet).call()
    print(f"Registered: {registered}")
    assert registered is True, f"Wallet {wallet} is not registered on-chain"

    # Read key hash
    key_hash = contract.functions.getKeyHash(wallet).call()
    print(f"Key hash: {key_hash.hex()}")

    # Read key version
    key_version = contract.functions.getKeyVersion(wallet).call()
    print(f"Key version: {key_version}")
    assert key_version >= 1

    print("Registry state: PASSED")
