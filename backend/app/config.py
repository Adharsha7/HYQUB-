"""
Centralized settings for the HYQUB PQ Verification Engine.
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "HYQUB PQ Verification Engine"
    version: str = "0.1.0"

    # Runtime environment.
    # Default is "production" — development mode must be opted into
    # explicitly in .env.  This prevents accidentally running with
    # development defaults in a deployed environment.
    environment: str = "production"

    # Explicit opt-in for development/diagnostic routes.
    #
    # /dev/generate-keypair and /dev/sign are only registered when
    # BOTH of these conditions hold:
    #
    #   1. enable_dev_tools is True
    #   2. the connected chain_id is 31337 (local Anvil)
    #
    # The application refuses to start if enable_dev_tools=True and
    # the chain is not 31337.  This prevents accidentally exposing
    # these routes against a real network.
    #
    # Default: False  (no dev routes in production)
    enable_dev_tools: bool = False

    # Frontend origins allowed to call this API.
    cors_origins: list[str] = ["http://localhost:3000"]

    # Verifier configuration.
    verifier_id: str = "verifier-a"
    required_quorum: int = 2

    # Blockchain signing keys.
    registrar_private_key: str
    approval_signer_private_key: str

    # Blockchain RPC.
    rpc_url: str = "http://127.0.0.1:8545"

    # HYQUB deployed contract addresses.
    entrypoint_address: str
    registry_address: str
    wallet_address: str
    test_target_address: str

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="HYQUB_",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
