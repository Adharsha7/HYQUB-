"""
Unit test configuration.

Unit tests must not require a live Anvil chain or running backend.

PROBLEM: The module-level `app = create_app()` in app/main.py calls
_assert_local_chain() when HYQUB_ENABLE_DEV_TOOLS=true, which does a
real web3 chain_id call.  This makes app.main unimportable during test
collection when Anvil isn't running.

SOLUTION: A pytest plugin hook (pytest_configure) is used to start a
web3.Web3 mock early enough to cover the import of app.main during
collection.  The mock is only started when the integration marker is NOT
the sole marker being run (i.e. when unit tests are collected).

The mock is stopped at session end via a finaliser so it does not leak
into integration tests when both suites are collected in the same run.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


def _make_mock_web3(chain_id: int = 31337):
    mock_w3 = MagicMock()
    mock_w3.is_connected.return_value = True
    mock_w3.eth.chain_id = chain_id
    return mock_w3


# Module-level patch instance — started in pytest_configure if needed.
_web3_patch = patch("web3.Web3", return_value=_make_mock_web3(31337))
_patch_started = False


def pytest_configure(config):
    """
    Start the web3 mock before any test module is imported.

    Only active when unit tests are being collected (i.e. not a pure
    `-m integration` run).  This lets app.main be imported during
    collection without a live Anvil connection.
    """
    global _patch_started

    # If the user explicitly asked for ONLY integration tests, leave
    # web3 alone so integration tests can make real connections.
    mark_expr = getattr(config.option, "markexpr", "")
    if mark_expr == "integration":
        return

    _web3_patch.start()
    _patch_started = True


def pytest_unconfigure(config):
    """Stop the mock when the session ends."""
    global _patch_started
    if _patch_started:
        try:
            _web3_patch.stop()
        except RuntimeError:
            pass  # already stopped
        _patch_started = False
