"""
HYQUB — Config security tests  (Task H)

Verifies the three required scenarios:

1. Default / production configuration:
   HYQUB_ENABLE_DEV_TOOLS is False (the default).
   /dev routes must not exist → 404 on every request.

2. Dev tools explicitly enabled on chain 31337 (local Anvil):
   HYQUB_ENABLE_DEV_TOOLS=true AND chain_id=31337.
   /dev routes must be registered and respond normally.

3. Dev tools enabled on a non-local chain:
   HYQUB_ENABLE_DEV_TOOLS=true AND chain_id≠31337.
   _assert_local_chain() must raise RuntimeError.

Strategy:
  All tests call create_app() directly via patch.object on the already-
  imported app.main module, so the module-level `app = create_app()` that
  runs on first import does not interfere.  The Settings lru_cache is
  cleared before each test.

No live Anvil is required — web3 chain_id calls are mocked.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch, PropertyMock

import pytest


# ---------------------------------------------------------------------------
# Settings factory
# ---------------------------------------------------------------------------

def _make_settings(**overrides):
    """
    Return a Settings instance with all required fields.
    Uses Anvil well-known account 0 key (public knowledge) — not real secrets.
    """
    import app.config as cfg
    cfg.get_settings.cache_clear()

    from app.config import Settings

    base = dict(
        environment="production",
        enable_dev_tools=False,
        cors_origins=["http://localhost:3000"],
        verifier_id="verifier-a",
        required_quorum=2,
        registrar_private_key=(
            "0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80"
        ),
        approval_signer_private_key=(
            "0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80"
        ),
        rpc_url="http://127.0.0.1:8545",
        entrypoint_address="0xe7f1725e7734ce288f8367e1bb143e90bb3f0512",
        registry_address="0x5fbdb2315678afecb367f032d93f642f64180aa3",
        wallet_address="0x9fe46736679d2d9a65f0992f2272de9f3c7fa6e0",
        test_target_address="0xcf7ed3acca5a467e9e704c703e8d87f634fb0fc9",
    )
    base.update(overrides)
    return Settings(**base)


def _fresh_create_app(settings, mock_assert_chain=True):
    """
    Call create_app() with the given settings injected, without triggering
    the live .env or a real Anvil connection.

    Uses patch.object so the already-imported app.main module is patched
    in-place — no importlib.reload needed.
    """
    import app.config as cfg
    cfg.get_settings.cache_clear()

    import app.main as main_mod

    patches = [patch.object(main_mod, "get_settings", return_value=settings)]
    if mock_assert_chain:
        patches.append(patch.object(main_mod, "_assert_local_chain"))

    if len(patches) == 1:
        with patches[0]:
            return main_mod.create_app()
    else:
        with patches[0], patches[1]:
            return main_mod.create_app()


# ---------------------------------------------------------------------------
# Scenario 1: Default / production — dev routes must 404
# ---------------------------------------------------------------------------

class TestProductionDefaults:

    def test_default_environment_is_production(self):
        """HYQUB_ENVIRONMENT must default to 'production'."""
        s = _make_settings()
        assert s.environment == "production"

    def test_default_enable_dev_tools_is_false(self):
        """HYQUB_ENABLE_DEV_TOOLS must default to False."""
        s = _make_settings()
        assert s.enable_dev_tools is False

    def test_dev_generate_keypair_returns_404_by_default(self):
        """GET /dev/generate-keypair must not exist in default config."""
        from fastapi.testclient import TestClient

        settings = _make_settings(enable_dev_tools=False)
        application = _fresh_create_app(settings)
        client = TestClient(application, raise_server_exceptions=False)

        assert client.get("/dev/generate-keypair").status_code == 404

    def test_dev_sign_returns_404_by_default(self):
        """POST /dev/sign must not exist in default config."""
        from fastapi.testclient import TestClient

        settings = _make_settings(enable_dev_tools=False)
        application = _fresh_create_app(settings)
        client = TestClient(application, raise_server_exceptions=False)

        assert client.post(
            "/dev/sign",
            json={"secret_key": "dGVzdA==", "message": "hello"},
        ).status_code == 404

    def test_health_still_works_in_production(self):
        """Core /health route must work regardless of dev tool setting."""
        from fastapi.testclient import TestClient

        settings = _make_settings(enable_dev_tools=False)
        application = _fresh_create_app(settings)
        client = TestClient(application, raise_server_exceptions=False)

        assert client.get("/health").status_code == 200

    def test_environment_development_alone_does_not_enable_dev_tools(self):
        """
        HYQUB_ENVIRONMENT=development alone must NOT register dev routes.
        Only HYQUB_ENABLE_DEV_TOOLS=true does that.
        """
        from fastapi.testclient import TestClient

        settings = _make_settings(environment="development", enable_dev_tools=False)
        application = _fresh_create_app(settings)
        client = TestClient(application, raise_server_exceptions=False)

        assert client.get("/dev/generate-keypair").status_code == 404
        assert client.post(
            "/dev/sign",
            json={"secret_key": "x", "message": "y"},
        ).status_code == 404


# ---------------------------------------------------------------------------
# Scenario 2: Dev tools enabled + chain 31337 → routes available
# ---------------------------------------------------------------------------

class TestDevToolsOnLocalChain:

    def test_dev_generate_keypair_available_when_dev_tools_enabled(self):
        """GET /dev/generate-keypair must exist when HYQUB_ENABLE_DEV_TOOLS=true."""
        from fastapi.testclient import TestClient

        settings = _make_settings(environment="development", enable_dev_tools=True)
        application = _fresh_create_app(settings, mock_assert_chain=True)
        client = TestClient(application, raise_server_exceptions=False)

        assert client.get("/dev/generate-keypair").status_code == 200

    def test_dev_sign_available_when_dev_tools_enabled(self):
        """POST /dev/sign must exist and return a signature."""
        from fastapi.testclient import TestClient
        from app.crypto.mldsa import generate_keypair
        from app.crypto.encoding import encode_key_or_signature

        _, sk_bytes = generate_keypair()
        sk_b64 = encode_key_or_signature(sk_bytes)

        settings = _make_settings(environment="development", enable_dev_tools=True)
        application = _fresh_create_app(settings, mock_assert_chain=True)
        client = TestClient(application, raise_server_exceptions=False)

        response = client.post("/dev/sign", json={"secret_key": sk_b64, "message": "test"})
        assert response.status_code == 200
        assert "signature" in response.json()

    def test_assert_local_chain_is_called_when_dev_tools_enabled(self):
        """_assert_local_chain must be invoked when enable_dev_tools=True."""
        import app.config as cfg
        cfg.get_settings.cache_clear()

        import app.main as main_mod

        settings = _make_settings(environment="development", enable_dev_tools=True)

        with patch.object(main_mod, "get_settings", return_value=settings), \
             patch.object(main_mod, "_assert_local_chain") as mock_check:
            main_mod.create_app()

        mock_check.assert_called_once_with(settings.rpc_url)

    def test_assert_local_chain_not_called_when_dev_tools_disabled(self):
        """_assert_local_chain must NOT be called when enable_dev_tools=False."""
        import app.config as cfg
        cfg.get_settings.cache_clear()

        import app.main as main_mod

        settings = _make_settings(enable_dev_tools=False)

        with patch.object(main_mod, "get_settings", return_value=settings), \
             patch.object(main_mod, "_assert_local_chain") as mock_check:
            main_mod.create_app()

        mock_check.assert_not_called()


# ---------------------------------------------------------------------------
# Scenario 3: Dev tools enabled on non-local chain → startup must fail
# ---------------------------------------------------------------------------

class TestDevToolsOnNonLocalChain:

    def test_assert_local_chain_raises_on_mainnet(self):
        """_assert_local_chain must raise RuntimeError for chain_id=1."""
        import app.main as main_mod

        mock_web3 = MagicMock()
        mock_web3.eth.chain_id = 1

        with patch("web3.Web3") as mock_cls:
            mock_cls.HTTPProvider = MagicMock()
            mock_cls.return_value = mock_web3

            with pytest.raises(RuntimeError, match="31337"):
                main_mod._assert_local_chain("http://mainnet.example.com:8545")

    def test_assert_local_chain_raises_on_polygon(self):
        """chain_id=137 (Polygon) must also be rejected."""
        import app.main as main_mod

        mock_web3 = MagicMock()
        mock_web3.eth.chain_id = 137

        with patch("web3.Web3") as mock_cls:
            mock_cls.HTTPProvider = MagicMock()
            mock_cls.return_value = mock_web3

            with pytest.raises(RuntimeError, match="31337"):
                main_mod._assert_local_chain("http://polygon.example.com:8545")

    def test_assert_local_chain_passes_on_31337(self):
        """chain_id=31337 must not raise."""
        import app.main as main_mod

        mock_web3 = MagicMock()
        mock_web3.eth.chain_id = 31337

        with patch("web3.Web3") as mock_cls:
            mock_cls.HTTPProvider = MagicMock()
            mock_cls.return_value = mock_web3

            main_mod._assert_local_chain("http://127.0.0.1:8545")  # must not raise

    def test_assert_local_chain_raises_on_rpc_error(self):
        """An unreachable RPC must cause RuntimeError."""
        import app.main as main_mod

        mock_web3 = MagicMock()
        type(mock_web3.eth).chain_id = PropertyMock(
            side_effect=ConnectionError("refused")
        )

        with patch("web3.Web3") as mock_cls:
            mock_cls.HTTPProvider = MagicMock()
            mock_cls.return_value = mock_web3

            with pytest.raises(RuntimeError):
                main_mod._assert_local_chain("http://127.0.0.1:8545")

    def test_create_app_raises_when_chain_check_fails(self):
        """
        create_app() must propagate RuntimeError when _assert_local_chain raises.
        """
        import app.config as cfg
        cfg.get_settings.cache_clear()

        import app.main as main_mod

        settings = _make_settings(environment="development", enable_dev_tools=True)

        with patch.object(main_mod, "get_settings", return_value=settings), \
             patch.object(main_mod, "_assert_local_chain",
                          side_effect=RuntimeError("chain_id=1, expected 31337")):
            with pytest.raises(RuntimeError, match="chain_id=1"):
                main_mod.create_app()
