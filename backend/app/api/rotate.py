import logging

from fastapi import APIRouter, HTTPException, status

from app.models.rotate import RotateKeyRequest, RotateKeyResponse
from app.services.rotate_service import (
    BlockchainRotationError,
    StorageDriftError,
    WalletNotRegisteredError,
    rotate_key,
)
from app.utils.storage import storage


logger = logging.getLogger(__name__)

router = APIRouter()


@router.post(
    "/rotate",
    response_model=RotateKeyResponse,
    status_code=status.HTTP_200_OK,
    summary="Rotate a wallet's ML-DSA public key",
)
def rotate(request: RotateKeyRequest) -> RotateKeyResponse:
    """
    Rotate the registered ML-DSA public key for an existing wallet.
    """

    try:
        return rotate_key(request, storage)

    except WalletNotRegisteredError as exc:
        logger.warning(
            "Rotation requested for unregistered wallet: %s",
            request.wallet_address,
        )

        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Wallet is not registered",
        ) from exc

    except BlockchainRotationError as exc:
        logger.error(
            "Blockchain rotation failed for %s: %s",
            request.wallet_address,
            exc,
        )

        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Blockchain key rotation failed",
        ) from exc

    except StorageDriftError as exc:
        logger.critical(
            "STATE DRIFT detected for %s: %s",
            request.wallet_address,
            exc,
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Wallet state synchronization failed",
        ) from exc

    except Exception:
        logger.exception(
            "Unexpected error during key rotation for %s",
            request.wallet_address,
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )
