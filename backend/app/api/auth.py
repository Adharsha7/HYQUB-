"""
HYQUB – Auth API
================

Exposes POST /auth/signup and POST /auth/login over HTTP.

Architecture — the same thin-route pattern used by api/register.py:

    Receive HTTP Request
        ↓
    Pydantic Validation    (FastAPI does this automatically)
        ↓
    Auth Service           (auth_service.signup / auth_service.login)
        ↓
    Account Service        (ensure_account — deploys wallet, registers key)
        ↓
    Return AuthResponse

This file does NOT:
  - hash passwords
  - touch the database directly
  - know anything about ML-DSA key generation or wallet deployment

All of that lives in app/services/auth_service.py and
app/services/account_service.py.

Error mapping
─────────────
  ValueError("Username already taken")  →  409 Conflict       (signup)
  ValueError("Invalid username …")      →  401 Unauthorized   (login)
  RuntimeError                          →  503 Service Unavailable
      (blockchain unreachable / deployment failed / key registration failed)
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

from app.models.auth import AuthResponse, LoginRequest, SignupRequest
from app.services.auth_service import login, signup

router = APIRouter(prefix="/auth", tags=["auth"])


def _to_auth_response(user: dict) -> AuthResponse:
    """
    Map the raw user dict returned by auth_service → AuthResponse.

    Raises 503 if the account provisioning step didn't complete
    (wallet_address or ml_dsa_public_key still NULL after ensure_account).
    """
    missing = [
        k for k in ("wallet_address", "ml_dsa_public_key", "key_version")
        if not user.get(k)
    ]
    if missing:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                f"Account provisioning incomplete — missing fields: "
                f"{', '.join(missing)}. Ensure Anvil is running and "
                f"the backend .env is correctly configured."
            ),
        )

    return AuthResponse(
        user_id=user["user_id"],
        username=user["username"],
        wallet_address=user["wallet_address"],
        ml_dsa_public_key=user["ml_dsa_public_key"],
        key_version=user["key_version"],
    )


@router.post(
    "/signup",
    response_model=AuthResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user account",
    description=(
        "Create a new username/password account. "
        "On success the backend automatically:\n"
        "1. Deploys a new HYQUBWallet contract and funds it with 1 ETH.\n"
        "2. Generates an ML-DSA-65 keypair and encrypts the secret key "
        "with the supplied password.\n"
        "3. Registers the public key hash in HYQUBRegistry on-chain.\n\n"
        "Returns the user identity including the deployed wallet address "
        "and the registered public key."
    ),
)
def auth_signup(request: SignupRequest) -> AuthResponse:
    """
    Sign up a new user and provision their smart account.

    Returns:
        201 Created with AuthResponse on success.

    Raises:
        409 Conflict if the username is already taken.
        503 Service Unavailable if wallet deployment or key
            registration fails (e.g., Anvil not running).
    """
    try:
        user = signup(request.username, request.password)
    except ValueError as exc:
        msg = str(exc)
        # "Username already taken" → 409; anything else is a bad request
        if "already taken" in msg.lower():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=msg,
            ) from exc
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=msg,
        ) from exc
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc

    return _to_auth_response(user)


@router.post(
    "/login",
    response_model=AuthResponse,
    status_code=status.HTTP_200_OK,
    summary="Authenticate an existing user account",
    description=(
        "Verify username + password, then return the user identity "
        "including their wallet address and current ML-DSA public key. "
        "If the wallet or keys were never provisioned (e.g., a legacy "
        "account), ensure_account runs automatically."
    ),
)
def auth_login(request: LoginRequest) -> AuthResponse:
    """
    Log in an existing user.

    Returns:
        200 OK with AuthResponse on success.

    Raises:
        401 Unauthorized if credentials are wrong.
        503 Service Unavailable if account provisioning fails.
    """
    try:
        user = login(request.username, request.password)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
        ) from exc
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc

    return _to_auth_response(user)
