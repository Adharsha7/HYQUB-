"""
Integration test configuration.

Provides an automatic skip guard: if Anvil is not reachable at
the configured RPC URL, all integration tests are skipped rather
than erroring during collection.

Uses a raw socket check rather than web3 so that the unit test
conftest's global web3.Web3 mock cannot interfere.
"""

from __future__ import annotations

import socket
import urllib.parse

import pytest

from app.config import get_settings


def _anvil_reachable() -> bool:
    """TCP-level check: is the RPC port open?"""
    try:
        settings = get_settings()
        parsed = urllib.parse.urlparse(settings.rpc_url)
        host = parsed.hostname or "127.0.0.1"
        port = parsed.port or 8545
        with socket.create_connection((host, port), timeout=3):
            return True
    except Exception:
        return False


# Apply skip to every test in this directory if Anvil is down.
def pytest_collection_modifyitems(config, items):
    if not _anvil_reachable():
        skip_no_anvil = pytest.mark.skip(
            reason="Anvil not reachable — skipping integration tests"
        )
        for item in items:
            if "integration" in str(item.fspath):
                item.add_marker(skip_no_anvil)
