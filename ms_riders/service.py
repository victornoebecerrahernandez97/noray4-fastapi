import asyncio
import logging
from datetime import datetime

import cloudinary
import cloudinary.uploader
from bson import ObjectId
from fastapi import HTTPException, UploadFile, status

from shared.config import settings
from shared.database import get_riders_collection

logger = logging.getLogger("noray4.riders")

_ALLOWED_AVATAR_MIME = {"image/jpeg", "image/png", "image/webp"}
_MAX_AVATAR_BYTES = 5 * 1024 * 1024  # 5 MB


def _serialize(doc: dict) -> dict:
    doc["_id"] = str(doc["_id"])
    return doc


async def get_rider_by_user_id(user_id: str) -> dict:
    collection = get_riders_collection()
    rider = await collection.find_one({"user_id": user_id})
    if not rider:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Rider no encontrado")
    return _serialize(rider)


async def get_rider_by_id(rider_id: str) -> dict:
    collection = get_riders_collection()
    try:
        oid = ObjectId(rider_id)
    except Exception:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="ID inválido")

    rider = await collection.find_one({"_id": oid})
    if not rider:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Rider no encontrado")
    return _serialize(rider)


async def create_rider(user_id: str, data: dict) -> dict:
    collection = get_riders_collection()

    existing = await collection.find_one({"user_id": user_id})
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Ya tienes un perfil de rider",
        )

    now = datetime.utcnow()
    doc = {
        "user_id": user_id,
        "followers": [],
        "following": [],
        "created_at": now,
        "updated_at": now,
        **data,
    }
    result = await collection.insert_one(doc)
    doc["_id"] = str(result.inserted_id)
    return doc


async def update_rider(user_id: str, updates: dict) -> dict:
    collection = get_riders_collection()

    updates["updated_at"] = datetime.utcnow()
    result = await collection.find_one_and_update(
        {"user_id": user_id},
        {"$set": updates},
        return_document=True,
    )
    if not result:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Rider no encontrado")
    return _serialize(result)


async def update_moto(user_id: str, moto: dict) -> dict:
    """Updates vehicle_model, vehicle_year, vehicle_km on the rider document."""
    collection = get_riders_collection()

    patch = {
        "vehicle_model": moto.get("modelo"),
        "vehicle_year": moto.get("año"),
        "vehicle_km": moto.get("km"),
        "updated_at": datetime.utcnow(),
    }
    result = await collection.find_one_and_update(
        {"user_id": user_id},
        {"$set": patch},
        return_document=True,
    )
    if not result:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Rider no encontrado")
    return _serialize(result)


async def follow_rider(follower_user_id: str, target_rider_id: str) -> dict:
    """Idempotent follow: adds follower_user_id to target's followers and target's user_id to follower's following."""
    collection = get_riders_collection()

    target = await get_rider_by_id(target_rider_id)
    target_user_id = target["user_id"]

    if follower_user_id == target_user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No puedes seguirte a ti mismo",
        )

    follower = await collection.find_one({"user_id": follower_user_id})
    if not follower:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Rider no encontrado")

    await collection.update_one(
        {"user_id": follower_user_id},
        {"$addToSet": {"following": target_user_id}, "$set": {"updated_at": datetime.utcnow()}},
    )
    await collection.update_one(
        {"user_id": target_user_id},
        {"$addToSet": {"followers": follower_user_id}, "$set": {"updated_at": datetime.utcnow()}},
    )

    return await get_rider_by_id(target_rider_id)


async def unfollow_rider(follower_user_id: str, target_rider_id: str) -> dict:
    """Removes follower_user_id from target's followers and target's user_id from follower's following."""
    collection = get_riders_collection()

    target = await get_rider_by_id(target_rider_id)
    target_user_id = target["user_id"]

    await collection.update_one(
        {"user_id": follower_user_id},
        {"$pull": {"following": target_user_id}, "$set": {"updated_at": datetime.utcnow()}},
    )
    await collection.update_one(
        {"user_id": target_user_id},
        {"$pull": {"followers": follower_user_id}, "$set": {"updated_at": datetime.utcnow()}},
    )

    return await get_rider_by_id(target_rider_id)


async def upload_avatar(user_id: str, file: UploadFile) -> dict:
    """Sube avatar a Cloudinary y actualiza avatar_url del rider."""
    collection = get_riders_collection()
    rider = await collection.find_one({"user_id": user_id})
    if not rider:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Rider no encontrado")

    if file.content_type not in _ALLOWED_AVATAR_MIME:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Formato no permitido (usa JPEG, PNG o WebP)",
        )
    data = await file.read()
    if len(data) > _MAX_AVATAR_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Máximo 5 MB",
        )

    cloudinary.config(
        cloud_name=settings.CLOUDINARY_CLOUD_NAME,
        api_key=settings.CLOUDINARY_API_KEY,
        api_secret=settings.CLOUDINARY_API_SECRET,
    )

    rider_id = str(rider["_id"])

    def _do_upload():
        return cloudinary.uploader.upload(
            data,
            folder=f"noray4/riders/{rider_id}",
            public_id="avatar",
            overwrite=True,
            resource_type="image",
            eager=[{
                "width": 400,
                "height": 400,
                "crop": "fill",
                "gravity": "face",
                "fetch_format": "auto",
                "quality": "auto",
            }],
            eager_async=False,
        )

    try:
        result = await asyncio.to_thread(_do_upload)
    except Exception as exc:
        logger.error("Cloudinary avatar upload error: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Error al subir el avatar",
        )

    eager = result.get("eager", [])
    avatar_url = eager[0]["secure_url"] if eager else result["secure_url"]

    updated = await collection.find_one_and_update(
        {"user_id": user_id},
        {"$set": {"avatar_url": avatar_url, "updated_at": datetime.utcnow()}},
        return_document=True,
    )
    return _serialize(updated)


_AVATAR_PRESETS = [
    {"id": "musico",    "label": "Músico",    "public_id": "musico_ux7tk5"},
    {"id": "nomada",    "label": "Nómada",    "public_id": "nomada_hry6tb"},
    {"id": "buscando",  "label": "Buscando",  "public_id": "buscando_kxeggo"},
    {"id": "gamberro",  "label": "Gamberro",  "public_id": "gamberro_vgrklc"},
    {"id": "wild",      "label": "Wild",      "public_id": "wild-animals_wqh76p"},
    {"id": "dusk",      "label": "Dusk",      "public_id": "dusk_pis4xh"},
]


def list_avatar_presets() -> list[dict]:
    """Genera URLs de presets desde Cloudinary con transformación 400x400 centrada."""
    cloud = settings.CLOUDINARY_CLOUD_NAME
    if not cloud:
        return []
    base = f"https://res.cloudinary.com/{cloud}/image/upload"
    transform = "c_fill,g_auto,h_400,w_400,f_auto,q_auto"
    return [
        {
            "id": p["id"],
            "label": p["label"],
            "url": f"{base}/{transform}/{p['public_id']}",
        }
        for p in _AVATAR_PRESETS
    ]


async def get_stats(rider_id: str) -> dict:
    await get_rider_by_id(rider_id)  # validates existence
    from ms_amarres.service import get_rider_stats
    from ms_groups.service import get_rider_group_count
    import asyncio
    stats, grupos = await asyncio.gather(
        get_rider_stats(rider_id),
        get_rider_group_count(rider_id),
    )
    return {**stats, "grupos": grupos}
