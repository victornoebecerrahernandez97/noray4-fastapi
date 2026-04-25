import logging

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from shared.auth import verify_token
from shared.database import get_riders_collection, get_users_collection

_bearer = HTTPBearer()
logger = logging.getLogger("noray4.dependencies")


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer),
) -> str:
    """Returns the user_id (str) extracted from the Bearer JWT."""
    payload = verify_token(credentials.credentials)
    user_id: str | None = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token sin sujeto válido",
        )
    return user_id


async def get_current_rider(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer),
) -> dict:
    """Returns the full Rider document for the authenticated user.

    For fresh guests (is_guest=True in JWT) without a rider yet, auto-creates the profile
    to handle race conditions between token issuance and first request.
    """
    payload = verify_token(credentials.credentials)
    user_id: str | None = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token sin sujeto válido",
        )

    collection = get_riders_collection()
    rider = await collection.find_one({"user_id": user_id})
    if rider:
        rider["_id"] = str(rider["_id"])
        return rider

    if payload.get("is_guest"):
        display_name: str = payload.get("display_name", "Invitado")
        logger.warning("GUEST rider missing for user_id=%s — auto-creating", user_id)
        try:
            from ms_riders.service import create_rider
            await create_rider(user_id, {"display_name": display_name})
        except HTTPException as exc:
            if exc.status_code != status.HTTP_409_CONFLICT:
                raise
        except Exception as exc:
            logger.error("Error auto-creating guest rider for %s: %s", user_id, exc)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Error al crear perfil de invitado",
            )
        rider = await collection.find_one({"user_id": user_id})
        if rider:
            rider["_id"] = str(rider["_id"])
            return rider

    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Perfil de rider no encontrado",
    )
