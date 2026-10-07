from pathlib import Path
import json

from fastapi import APIRouter, HTTPException
from web3 import Web3

from app.utils.blockchain import (
    get_web3,
    get_registry_contract,
)

router = APIRouter(prefix="/wallet", tags=["wallet"])


@router.get("/{wallet_address}/state")
def get_wallet_state(wallet_address: str):
    """
    Read live HYQUB wallet state from the blockchain.
    """

    if not Web3.is_address(wallet_address):
        raise HTTPException(
            status_code=400,
            detail="Invalid wallet address",
        )

    wallet = Web3.to_checksum_address(wallet_address)

    try:
        web3 = get_web3()

        # Live blockchain state
        balance_wei = web3.eth.get_balance(wallet)
        chain_id = web3.eth.chain_id
        block_number = web3.eth.block_number

        # Load the ABI of the DEPLOYED HYQUBWallet
        abi_path = (
            Path(__file__).resolve().parents[3]
            / "blockchain"
            / "out"
            / "HYQUBWallet.sol"
            / "HYQUBWallet.json"
        )

        with open(abi_path, "r") as f:
            wallet_artifact = json.load(f)

        wallet_contract = web3.eth.contract(
            address=wallet,
            abi=wallet_artifact["abi"],
        )

        owner = wallet_contract.functions.owner().call()
        nonce = wallet_contract.functions.nonce().call()

        # Live HYQUB registry state
        registry = get_registry_contract(web3)

        registered = registry.functions.isRegistered(wallet).call()
        key_version = registry.functions.getKeyVersion(wallet).call()

        return {
            "wallet_address": wallet,
            "owner": owner,
            "balance_wei": str(balance_wei),
            "balance_eth": str(Web3.from_wei(balance_wei, "ether")),
            "nonce": nonce,
            "chain_id": chain_id,
            "block_number": block_number,
            "registered": registered,
            "key_version": key_version,
        }

    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Unable to read wallet state: {exc}",
        )
