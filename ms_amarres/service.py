"""
ms_amarres/service.py — Memoria de viajes Noray4.

Flujo principal:
  1. close_sala() en MS-Salas llama create_amarre_from_sala() → amarre automático con GPX
  2. El rider puede crear amarres manuales, agregar fotos, editar, clonar y compartir
"""
import asyncio
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

import cloudinary
import cloudinary.uploader
from bson import ObjectId
from fastapi import HTTPException, UploadFile, status
from pymongo import ASCENDING, DESCENDING

from shared.config import settings
from shared.database import get_amarres_collection
from ms_amarres.schemas import AmarreCreate, AmarreUpdate

logger = logging.getLogger("noray4.amarres")

_ALLOWED_MIME = {"image/jpeg", "image/png", "image/webp"}
_MAX_UPLOAD_BYTES = 10 * 1024 * 1024
_MAX_FOTOS = 50

_FULL_PROJECTION = {
    "_id": 1, "sala_id": 1, "owner_id": 1, "title": 1, "description": 1,
    "riders": 1, "riders_display": 1, "gpx_data": 1, "km_total": 1,
    "duracion_min": 1, "fotos": 1, "playlist": 1, "chat_log": 1,
    "privacy": 1, "tags": 1, "cloned_from": 1, "clone_count": 1,
    "likes": 1, "created_at": 1, "updated_at": 1,
}

_PUBLIC_PROJECTION = {
    "_id": 1, "owner_id": 1, "title": 1, "description": 1,
    "riders_display": 1, "km_total": 1, "duracion_min": 1,
    "fotos": 1, "privacy": 1, "tags": 1, "clone_count": 1,
    "likes": 1, "created_at": 1,
}


# ---------------------------------------------------------------------------
# Startup — índices
# ---------------------------------------------------------------------------

async def ensure_amarre_indexes() -> None:
    col = get_amarres_collection()
    await col.create_index(
        [("owner_id", ASCENDING), ("created_at", DESCENDING)],
        name="owner_created_at", background=True,
    )
    await col.create_index(
        [("privacy", ASCENDING), ("created_at", DESCENDING)],
        name="privacy_created_at", background=True,
    )
    await col.create_index([("sala_id", ASCENDING)], name="amarre_sala_id", background=True)
    await col.create_index([("riders", ASCENDING)], name="amarre_riders", background=True)
    logger.info("Índices de amarres verificados")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _oid(value: str, label: str = "ID") -> ObjectId:
    try:
        return ObjectId(value)
    except Exception:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"{label} inválido")


def _serialize(doc: dict) -> dict:
    doc["_id"] = str(doc["_id"])
    return doc


async def _get_amarre_raw(amarre_id: str) -> dict:
    col = get_amarres_collection()
    doc = await col.find_one({"_id": _oid(amarre_id, "ID de amarre")}, _FULL_PROJECTION)
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Amarre no encontrado")
    return _serialize(doc)


def _check_access(amarre: dict, rider_id: str) -> None:
    privacy = amarre["privacy"]
    if privacy == "public":
        return
    if privacy == "private" and amarre["owner_id"] != rider_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Amarre privado")
    if privacy == "group" and rider_id not in amarre.get("riders", []):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Solo participantes pueden ver este amarre")


def _calc_km(gpx_data: Optional[dict]) -> float:
    """Estima km totales sumando distancias haversine entre puntos del primer rider."""
    if not gpx_data or not gpx_data.get("riders"):
        return 0.0
    import math
    def haversine(p1, p2) -> float:
        R = 6371.0
        lat1, lon1 = math.radians(p1["lat"]), math.radians(p1["lng"])
        lat2, lon2 = math.radians(p2["lat"]), math.radians(p2["lng"])
        dlat, dlon = lat2 - lat1, lon2 - lon1
        a = math.sin(dlat/2)**2 + math.cos(lat1)*math.cos(lat2)*math.sin(dlon/2)**2
        return R * 2 * math.asin(math.sqrt(a))

    total = 0.0
    for rider_track in gpx_data["riders"]:
        pts = rider_track.get("points", [])
        for i in range(1, len(pts)):
            try:
                total += haversine(pts[i-1], pts[i])
            except Exception:
                pass
    return round(total, 2)


def _calc_duracion(gpx_data: Optional[dict]) -> int:
    """Calcula duración en minutos desde el primer al último timestamp del track."""
    if not gpx_data or not gpx_data.get("riders"):
        return 0
    timestamps = []
    for rider_track in gpx_data["riders"]:
        for pt in rider_track.get("points", []):
            ts = pt.get("timestamp")
            if ts:
                try:
                    if isinstance(ts, str):
                        from datetime import timezone
                        ts = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                    timestamps.append(ts)
                except Exception:
                    pass
    if len(timestamps) < 2:
        return 0
    delta = max(timestamps) - min(timestamps)
    return max(0, int(delta.total_seconds() / 60))


# ---------------------------------------------------------------------------
# Creación
# ---------------------------------------------------------------------------

async def create_amarre_from_sala(
    sala_id: str,
    owner_id: str,
    riders: List[str],
    riders_display: List[dict],
) -> dict:
    """Creación automática al cerrar sala. Exporta GPX, calcula stats y limpia stores."""
    from ms_location.track_store import track_store
    from ms_voice.ptt_store import ptt_store

    gpx = track_store.export_gpx(sala_id)
    gpx_data = gpx.model_dump(mode="json")
    km_total = _calc_km(gpx_data)
    duracion_min = _calc_duracion(gpx_data)

    track_store.clear_sala(sala_id)
    ptt_store.cleanup_sala(sala_id)

    now = datetime.utcnow()
    doc = {
        "sala_id": sala_id,
        "owner_id": owner_id,
        "title": f"Ruta {now.strftime('%d/%m/%Y')}",
        "description": None,
        "riders": riders,
        "riders_display": riders_display,
        "gpx_data": gpx_data,
        "km_total": km_total,
        "duracion_min": duracion_min,
        "fotos": [],
        "playlist": [],
        "chat_log": None,
        "privacy": "group",
        "tags": [],
        "cloned_from": None,
        "clone_count": 0,
        "likes": [],
        "created_at": now,
        "updated_at": None,
    }
    col = get_amarres_collection()
    result = await col.insert_one(doc)
    doc["_id"] = str(result.inserted_id)
    logger.info("Amarre auto-creado — sala=%s km=%.1f min=%d", sala_id, km_total, duracion_min)
    return doc


async def create_amarre_manual(owner_id: str, display_name: str, data: AmarreCreate) -> dict:
    now = datetime.utcnow()
    doc = {
        "sala_id": None,
        "owner_id": owner_id,
        "title": data.title,
        "description": data.description,
        "riders": [owner_id],
        "riders_display": [{"rider_id": owner_id, "display_name": display_name}],
        "gpx_data": None,
        "km_total": 0.0,
        "duracion_min": 0,
        "fotos": [],
        "playlist": [],
        "chat_log": None,
        "privacy": data.privacy,
        "tags": data.tags,
        "cloned_from": None,
        "clone_count": 0,
        "likes": [],
        "created_at": now,
        "updated_at": None,
    }
    col = get_amarres_collection()
    result = await col.insert_one(doc)
    doc["_id"] = str(result.inserted_id)
    return doc


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------

async def get_amarre(amarre_id: str, rider_id: str) -> dict:
    amarre = await _get_amarre_raw(amarre_id)
    _check_access(amarre, rider_id)
    return amarre


async def update_amarre(amarre_id: str, rider_id: str, data: AmarreUpdate) -> dict:
    amarre = await _get_amarre_raw(amarre_id)
    if amarre["owner_id"] != rider_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Solo el owner puede editar")

    patch = data.model_dump(exclude_none=True)
    if "playlist" in patch:
        patch["playlist"] = [p.model_dump() if hasattr(p, "model_dump") else p for p in (data.playlist or [])]
    if not patch:
        return amarre

    patch["updated_at"] = datetime.utcnow()
    col = get_amarres_collection()
    result = await col.find_one_and_update(
        {"_id": _oid(amarre_id)},
        {"$set": patch},
        projection=_FULL_PROJECTION,
        return_document=True,
    )
    return _serialize(result)


async def delete_amarre(amarre_id: str, rider_id: str) -> dict:
    amarre = await _get_amarre_raw(amarre_id)
    if amarre["owner_id"] != rider_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Solo el owner puede eliminar")
    col = get_amarres_collection()
    await col.delete_one({"_id": _oid(amarre_id)})
    return {"status": "ok", "detail": "Amarre eliminado"}


# ---------------------------------------------------------------------------
# Fotos
# ---------------------------------------------------------------------------

def _configure_cloudinary() -> None:
    cloudinary.config(
        cloud_name=settings.CLOUDINARY_CLOUD_NAME,
        api_key=settings.CLOUDINARY_API_KEY,
        api_secret=settings.CLOUDINARY_API_SECRET,
    )


async def add_foto(amarre_id: str, rider_id: str, file: UploadFile, caption: Optional[str]) -> dict:
    amarre = await _get_amarre_raw(amarre_id)
    if rider_id not in amarre.get("riders", []):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Solo participantes pueden añadir fotos")
    if len(amarre.get("fotos", [])) >= _MAX_FOTOS:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=f"Máximo {_MAX_FOTOS} fotos por amarre")
    if file.content_type not in _ALLOWED_MIME:
        raise HTTPException(status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail="Formato no permitido. Acepta: jpeg, png, webp")

    data = await file.read()
    if len(data) > _MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="Máximo 10 MB")

    _configure_cloudinary()

    def _do_upload():
        return cloudinary.uploader.upload(
            data,
            folder=f"noray4/amarres/{amarre_id}",
            resource_type="image",
            eager=[{"width": 600, "crop": "scale", "fetch_format": "auto"}],
            eager_async=False,
        )

    try:
        result = await asyncio.to_thread(_do_upload)
    except Exception as exc:
        logger.error("Cloudinary upload error: %s", exc)
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Error al subir la foto")

    eager = result.get("eager", [])
    foto = {
        "url": result["secure_url"],
        "thumb_url": eager[0]["secure_url"] if eager else result["secure_url"],
        "public_id": result["public_id"],
        "rider_id": rider_id,
        "caption": caption,
        "taken_at": datetime.utcnow().isoformat(),
    }

    col = get_amarres_collection()
    updated = await col.find_one_and_update(
        {"_id": _oid(amarre_id)},
        {"$push": {"fotos": foto}, "$set": {"updated_at": datetime.utcnow()}},
        projection=_FULL_PROJECTION,
        return_document=True,
    )
    return _serialize(updated)


async def delete_foto(amarre_id: str, rider_id: str, public_id: str) -> dict:
    amarre = await _get_amarre_raw(amarre_id)
    foto = next((f for f in amarre.get("fotos", []) if f["public_id"] == public_id), None)
    if not foto:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Foto no encontrada")
    if foto["rider_id"] != rider_id and amarre["owner_id"] != rider_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Solo quien subió la foto o el owner pueden eliminarla")

    col = get_amarres_collection()
    updated = await col.find_one_and_update(
        {"_id": _oid(amarre_id)},
        {"$pull": {"fotos": {"public_id": public_id}}, "$set": {"updated_at": datetime.utcnow()}},
        projection=_FULL_PROJECTION,
        return_document=True,
    )
    return _serialize(updated)


# ---------------------------------------------------------------------------
# Social
# ---------------------------------------------------------------------------

async def like_amarre(amarre_id: str, rider_id: str) -> dict:
    amarre = await _get_amarre_raw(amarre_id)
    if amarre["privacy"] != "public":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Solo se puede dar like a amarres públicos")

    col = get_amarres_collection()
    has_like = rider_id in amarre.get("likes", [])
    op = "$pull" if has_like else "$addToSet"
    result = await col.find_one_and_update(
        {"_id": _oid(amarre_id)},
        {op: {"likes": rider_id}},
        projection={"_id": 1, "likes": 1},
        return_document=True,
    )
    return {"amarre_id": amarre_id, "likes": len(result.get("likes", [])), "liked": not has_like}


async def clone_amarre(amarre_id: str, rider_id: str, display_name: str) -> dict:
    original = await _get_amarre_raw(amarre_id)
    _check_access(original, rider_id)

    now = datetime.utcnow()
    doc = {
        "sala_id": None,
        "owner_id": rider_id,
        "title": original["title"],
        "description": original.get("description"),
        "riders": [rider_id],
        "riders_display": [{"rider_id": rider_id, "display_name": display_name}],
        "gpx_data": original.get("gpx_data"),
        "km_total": original.get("km_total", 0.0),
        "duracion_min": original.get("duracion_min", 0),
        "fotos": [],
        "playlist": original.get("playlist", []),
        "chat_log": None,
        "privacy": "private",
        "tags": original.get("tags", []),
        "cloned_from": amarre_id,
        "clone_count": 0,
        "likes": [],
        "created_at": now,
        "updated_at": None,
    }
    col = get_amarres_collection()
    result = await col.insert_one(doc)
    doc["_id"] = str(result.inserted_id)

    # Incremento atómico — sin race condition
    await col.update_one({"_id": _oid(amarre_id)}, {"$inc": {"clone_count": 1}})

    return {"original_id": amarre_id, "amarre": doc}


# ---------------------------------------------------------------------------
# Listados
# ---------------------------------------------------------------------------

async def get_mis_amarres(rider_id: str, skip: int = 0, limit: int = 20) -> dict:
    limit = min(limit, 50)
    col = get_amarres_collection()
    f = {"owner_id": rider_id}
    total, docs = await asyncio.gather(
        col.count_documents(f),
        _fetch(col, f, _FULL_PROJECTION, skip, limit),
    )
    return {"items": docs, "total": total, "skip": skip, "limit": limit, "has_more": (skip + limit) < total}


async def get_amarres_publicos(skip: int = 0, limit: int = 20) -> dict:
    limit = min(limit, 50)
    col = get_amarres_collection()
    f = {"privacy": "public"}
    total, docs = await asyncio.gather(
        col.count_documents(f),
        _fetch(col, f, _PUBLIC_PROJECTION, skip, limit),
    )
    return {"items": docs, "total": total, "skip": skip, "limit": limit, "has_more": (skip + limit) < total}


async def get_amarres_by_sala(sala_id: str) -> List[dict]:
    col = get_amarres_collection()
    cursor = col.find({"sala_id": sala_id}, _FULL_PROJECTION).sort("created_at", DESCENDING)
    return [_serialize(doc) async for doc in cursor]


async def _fetch(col, query: dict, projection: dict, skip: int, limit: int) -> List[dict]:
    cursor = col.find(query, projection).sort("created_at", DESCENDING).skip(skip).limit(limit)
    return [_serialize(doc) async for doc in cursor]


# ---------------------------------------------------------------------------
# Stats para MS-Riders
# ---------------------------------------------------------------------------

async def get_rider_stats(rider_id: str) -> dict:
    """Retorna amarres reales para ms_riders/service.get_stats()."""
    col = get_amarres_collection()
    pipeline = [
        {"$match": {"riders": rider_id}},
        {"$group": {"_id": None, "count": {"$sum": 1}, "km": {"$sum": "$km_total"}}},
    ]
    results = await col.aggregate(pipeline).to_list(1)
    if results:
        return {"amarres": results[0]["count"], "km_totales": round(results[0]["km"], 1)}
    return {"amarres": 0, "km_totales": 0.0}
