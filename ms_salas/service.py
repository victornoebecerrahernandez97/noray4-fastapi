import logging
import secrets
from datetime import datetime
from typing import List, Optional

from bson import ObjectId
from fastapi import HTTPException, status

from shared.database import get_salas_collection
from ms_salas.schemas import SalaCreate, SalaUpdate

logger = logging.getLogger("noray4.salas")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _oid(sala_id: str) -> ObjectId:
    try:
        return ObjectId(sala_id)
    except Exception:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="ID de sala inválido")


def _serialize(doc: dict) -> dict:
    doc["_id"] = str(doc["_id"])
    return doc


async def _require_sala(sala_id: str) -> dict:
    collection = get_salas_collection()
    sala = await collection.find_one({"_id": _oid(sala_id)})
    if not sala:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Salida no encontrada")
    return _serialize(sala)


def _require_admin(sala: dict, rider_id: str) -> None:
    if sala["owner_id"] != rider_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Solo el admin puede realizar esta acción",
        )


def _is_member(sala: dict, rider_id: str) -> bool:
    return any(m["rider_id"] == rider_id for m in sala.get("miembros", []))


# ---------------------------------------------------------------------------
# Service functions
# ---------------------------------------------------------------------------

async def create_sala(owner_rider_id: str, owner_display_name: str, data: SalaCreate) -> dict:
    collection = get_salas_collection()

    qr_token = secrets.token_urlsafe(16)
    now = datetime.utcnow()

    doc = {
        "name": data.name,
        "description": data.description,
        "owner_id": owner_rider_id,
        "status": "active",
        "is_private": data.is_private,
        "miembros": [
            {
                "rider_id": owner_rider_id,
                "display_name": owner_display_name,
                "role": "admin",
                "joined_at": now,
            }
        ],
        "qr_token": qr_token,
        "invite_link": None,  # filled after insert_one so we have the sala_id
        "created_at": now,
        "closed_at": None,
    }

    result = await collection.insert_one(doc)
    sala_id = str(result.inserted_id)
    invite_link = f"https://noray4.app/sala/{sala_id}?token={qr_token}"

    await collection.update_one(
        {"_id": result.inserted_id},
        {"$set": {"invite_link": invite_link}},
    )

    doc["_id"] = sala_id
    doc["invite_link"] = invite_link

    # Crear canales de voz default — import local para evitar circular imports
    try:
        from ms_voice.service import create_default_canales
        await create_default_canales(sala_id, owner_rider_id)
    except Exception as exc:
        logger.warning("No se pudieron crear canales de voz para sala %s: %s", sala_id, exc)

    return doc


async def get_salas_activas(skip: int = 0, limit: int = 20) -> List[dict]:
    collection = get_salas_collection()
    cursor = (
        collection.find({"status": "active"})
        .sort("created_at", -1)
        .skip(skip)
        .limit(limit)
    )
    salas = []
    async for doc in cursor:
        salas.append(_serialize(doc))
    return salas


async def get_sala_by_id(sala_id: str) -> dict:
    return await _require_sala(sala_id)


async def update_sala(sala_id: str, rider_id: str, data: SalaUpdate) -> dict:
    sala = await _require_sala(sala_id)
    _require_admin(sala, rider_id)

    patch = data.model_dump(exclude_none=True)
    if not patch:
        return sala

    collection = get_salas_collection()
    result = await collection.find_one_and_update(
        {"_id": _oid(sala_id)},
        {"$set": patch},
        return_document=True,
    )
    return _serialize(result)


async def join_sala(
    sala_id: str,
    rider_id: str,
    display_name: str,
    qr_token: Optional[str] = None,
) -> dict:
    sala = await _require_sala(sala_id)

    if sala["status"] == "closed":
        raise HTTPException(status_code=status.HTTP_410_GONE, detail="La salida está cerrada")

    if sala["is_private"]:
        if not qr_token or qr_token != sala.get("qr_token"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Token de invitación inválido o requerido",
            )

    # Idempotent: already a member → return sala as-is
    if _is_member(sala, rider_id):
        return sala

    new_member = {
        "rider_id": rider_id,
        "display_name": display_name,
        "role": "rider",
        "joined_at": datetime.utcnow(),
    }

    collection = get_salas_collection()
    result = await collection.find_one_and_update(
        {"_id": _oid(sala_id)},
        {"$push": {"miembros": new_member}},
        return_document=True,
    )
    return _serialize(result)


async def close_sala(sala_id: str, rider_id: str) -> dict:
    sala = await _require_sala(sala_id)
    _require_admin(sala, rider_id)

    if sala["status"] == "closed":
        return sala

    collection = get_salas_collection()
    result = await collection.find_one_and_update(
        {"_id": _oid(sala_id)},
        {"$set": {"status": "closed", "closed_at": datetime.utcnow()}},
        return_document=True,
    )
    closed_sala = _serialize(result)

    # Crear amarre automático — import local para evitar circular imports
    try:
        from ms_amarres.service import create_amarre_from_sala
        riders = [m["rider_id"] for m in closed_sala.get("miembros", [])]
        riders_display = [
            {"rider_id": m["rider_id"], "display_name": m["display_name"]}
            for m in closed_sala.get("miembros", [])
        ]
        amarre = await create_amarre_from_sala(sala_id, rider_id, riders, riders_display)
        return {"sala": closed_sala, "amarre": amarre}
    except Exception as exc:
        logger.warning("No se pudo crear amarre para sala %s: %s", sala_id, exc)
        return closed_sala


async def get_qr(sala_id: str, rider_id: str) -> dict:
    sala = await _require_sala(sala_id)

    if not _is_member(sala, rider_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Debes ser miembro de la salida para ver el QR",
        )

    return {
        "qr_token": sala["qr_token"],
        "invite_link": sala["invite_link"],
    }


async def get_miembros(sala_id: str) -> List[dict]:
    sala = await _require_sala(sala_id)
    return sala.get("miembros", [])
