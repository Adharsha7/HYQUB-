"""
Unit tests for POST /auth/signup and POST /auth/login.

These tests run without Anvil (unit mark, no blockchain).
auth_service.signup and auth_service.login are mocked — we test
only HTTP status codes, response shapes, and error-to-status mapping.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

# app is created at module import time in app.main.
# The unit conftest already patches Web3 before this import runs.
from app.main import app

client = TestClient(app)

# ---------------------------------------------------------------------------
# Shared dummy user dict returned by mocked signup / login
# ---------------------------------------------------------------------------
_DUMMY_USER = {
    "user_id": 1,
    "username": "alice",
    "wallet_address": "0xAbCdEf0123456789AbCdEf0123456789AbCdEf01",
    "ml_dsa_public_key": "dGVzdHB1YmtleQ==",  # base64 "testpubkey"
    "encrypted_secret_key": "c29tZWJsb2I=",
    "password_hash": "hash",
    "password_salt": "salt",
    "key_version": 1,
}


# ---------------------------------------------------------------------------
# /auth/signup
# ---------------------------------------------------------------------------

class TestAuthSignup:
    def test_signup_success_returns_201_and_auth_response(self):
        with patch("app.api.auth.signup", return_value=_DUMMY_USER):
            resp = client.post(
                "/auth/signup",
                json={"username": "alice", "password": "supersecret"},
            )
        assert resp.status_code == 201
        body = resp.json()
        assert body["user_id"] == 1
        assert body["username"] == "alice"
        assert body["wallet_address"] == _DUMMY_USER["wallet_address"]
        assert body["ml_dsa_public_key"] == _DUMMY_USER["ml_dsa_public_key"]
        assert body["key_version"] == 1
        # Sensitive fields must NOT be in the response
        assert "encrypted_secret_key" not in body
        assert "password_hash" not in body

    def test_signup_duplicate_username_returns_409(self):
        with patch(
            "app.api.auth.signup",
            side_effect=ValueError("Username already taken: alice"),
        ):
            resp = client.post(
                "/auth/signup",
                json={"username": "alice", "password": "supersecret"},
            )
        assert resp.status_code == 409
        assert "already taken" in resp.json()["detail"]

    def test_signup_blockchain_failure_returns_503(self):
        with patch(
            "app.api.auth.signup",
            side_effect=RuntimeError("HYQUBWallet deployment transaction failed"),
        ):
            resp = client.post(
                "/auth/signup",
                json={"username": "alice", "password": "supersecret"},
            )
        assert resp.status_code == 503

    def test_signup_missing_password_returns_422(self):
        resp = client.post("/auth/signup", json={"username": "alice"})
        assert resp.status_code == 422

    def test_signup_password_too_short_returns_422(self):
        # min_length=8 in SignupRequest
        resp = client.post(
            "/auth/signup",
            json={"username": "alice", "password": "short"},
        )
        assert resp.status_code == 422

    def test_signup_empty_username_returns_422(self):
        resp = client.post(
            "/auth/signup",
            json={"username": "", "password": "supersecret"},
        )
        assert resp.status_code == 422

    def test_signup_provisioning_incomplete_returns_503(self):
        """
        If ensure_account returns a user dict without wallet_address
        (e.g., Anvil was unreachable but no exception was raised),
        the route should surface a 503.
        """
        incomplete_user = {**_DUMMY_USER, "wallet_address": None}
        with patch("app.api.auth.signup", return_value=incomplete_user):
            resp = client.post(
                "/auth/signup",
                json={"username": "alice", "password": "supersecret"},
            )
        assert resp.status_code == 503
        assert "provisioning incomplete" in resp.json()["detail"].lower()


# ---------------------------------------------------------------------------
# /auth/login
# ---------------------------------------------------------------------------

class TestAuthLogin:
    def test_login_success_returns_200_and_auth_response(self):
        with patch("app.api.auth.login", return_value=_DUMMY_USER):
            resp = client.post(
                "/auth/login",
                json={"username": "alice", "password": "supersecret"},
            )
        assert resp.status_code == 200
        body = resp.json()
        assert body["user_id"] == 1
        assert body["username"] == "alice"
        assert body["wallet_address"] == _DUMMY_USER["wallet_address"]
        assert "encrypted_secret_key" not in body

    def test_login_wrong_credentials_returns_401(self):
        with patch(
            "app.api.auth.login",
            side_effect=ValueError("Invalid username or password"),
        ):
            resp = client.post(
                "/auth/login",
                json={"username": "alice", "password": "wrongpassword"},
            )
        assert resp.status_code == 401
        assert "Invalid" in resp.json()["detail"]

    def test_login_blockchain_failure_returns_503(self):
        with patch(
            "app.api.auth.login",
            side_effect=RuntimeError("Could not reach RPC"),
        ):
            resp = client.post(
                "/auth/login",
                json={"username": "alice", "password": "supersecret"},
            )
        assert resp.status_code == 503

    def test_login_missing_fields_returns_422(self):
        resp = client.post("/auth/login", json={"username": "alice"})
        assert resp.status_code == 422

    def test_login_empty_body_returns_422(self):
        resp = client.post("/auth/login", json={})
        assert resp.status_code == 422
