from datetime import datetime

from bson import ObjectId
from fastapi import HTTPException, status

from shared.database import get_riders_collection


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
