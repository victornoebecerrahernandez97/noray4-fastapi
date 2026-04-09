from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from shared.auth import verify_token
from shared.database import get_riders_collection, get_users_collection

_bearer = HTTPBearer()


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
    user_id: str = Depends(get_current_user),
) -> dict:
    """Returns the full Rider document for the authenticated user."""
    collection = get_riders_collection()
    rider = await collection.find_one({"user_id": user_id})
    if not rider:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Perfil de rider no encontrado",
        )
    rider["_id"] = str(rider["_id"])
    return rider
