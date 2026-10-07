"""
HYQUB — pytest shared configuration and fixtures.

Fixtures defined here are available to all tests in tests/unit/
and tests/integration/.
"""

from __future__ import annotations

import pytest

from app.config import get_settings


@pytest.fixture(scope="session")
def settings():
    """Return the application settings (reads from backend/.env)."""
    return get_settings()
