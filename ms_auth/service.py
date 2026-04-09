import logging
from datetime import datetime, timedelta

from bson import ObjectId
from fastapi import HTTPException, status

from shared.auth import create_access_token, hash_password, verify_password
from shared.database import get_users_collection

logger = logging.getLogger("noray4.auth")


async def register_user(email: str, password: str, display_name: str) -> dict:
    collection = get_users_collection()

    existing = await collection.find_one({"email": email})
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Ya existe una cuenta con ese correo",
        )

    now = datetime.utcnow()
    doc = {
        "email": email,
        "hashed_password": hash_password(password),
        "display_name": display_name,
        "is_guest": False,
        "is_active": True,
        "created_at": now,
        "updated_at": now,
    }
    result = await collection.insert_one(doc)
    user_id = str(result.inserted_id)

    # Auto-create rider profile — import here to avoid circular imports at module load
    try:
        from ms_riders.service import create_rider
        await create_rider(user_id, {"display_name": display_name})
    except HTTPException as exc:
        # 409 means the rider already exists — safe to ignore
        if exc.status_code != status.HTTP_409_CONFLICT:
            logger.warning("No se pudo crear el perfil de rider para %s: %s", user_id, exc.detail)
    except Exception as exc:
        logger.warning("Error inesperado al crear rider para %s: %s", user_id, exc)

    token = create_access_token({"sub": user_id})
    return {"access_token": token, "token_type": "bearer"}


async def login_user(email: str, password: str) -> dict:
    collection = get_users_collection()

    user = await collection.find_one({"email": email, "is_guest": False})
    if not user or not verify_password(password, user.get("hashed_password", "")):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciales incorrectas",
        )
    if not user.get("is_active", True):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cuenta desactivada",
        )

    token = create_access_token({"sub": str(user["_id"])})
    return {"access_token": token, "token_type": "bearer"}


async def get_user_by_id(user_id: str) -> dict:
    collection = get_users_collection()
    try:
        oid = ObjectId(user_id)
    except Exception:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="ID inválido")

    user = await collection.find_one({"_id": oid})
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuario no encontrado")

    user["_id"] = str(user["_id"])
    return user


async def create_guest_token() -> dict:
    """Generates a 24-hour temporary token for QR/invite access."""
    collection = get_users_collection()

    now = datetime.utcnow()
    doc = {
        "email": f"guest_{ObjectId()}@noray4.guest",
        "hashed_password": None,
        "display_name": "Invitado",
        "is_guest": True,
        "is_active": True,
        "created_at": now,
        "updated_at": now,
    }
    result = await collection.insert_one(doc)
    user_id = str(result.inserted_id)

    token = create_access_token({"sub": user_id}, expires_delta=timedelta(hours=24))
    return {"access_token": token, "token_type": "bearer"}
