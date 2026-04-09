"""
ms_groups/service.py — Grupos permanentes y comunidades rider.

Decisiones de escalabilidad:
- stats desnormalizado en el documento: riders_count, km_total, amarres_count
  → no aggregation en cada request, recalc_stats() solo bajo demanda
- Text index en MongoDB para search — nunca regex full-scan
- $addToSet / $pull para membresía — operaciones atómicas
- Cloudinary upload en asyncio.to_thread()
"""
import asyncio
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

import cloudinary
import cloudinary.uploader
from bson import ObjectId
from fastapi import HTTPException, UploadFile, status
from pymongo import ASCENDING, DESCENDING, TEXT

from shared.config import settings
from shared.database import get_amarres_collection, get_grupos_collection, get_salas_collection
from ms_groups.schemas import GrupoCreate, GrupoUpdate

logger = logging.getLogger("noray4.groups")

_ALLOWED_MIME = {"image/jpeg", "image/png", "image/webp"}
_MAX_UPLOAD_BYTES = 5 * 1024 * 1024  # 5 MB para logos

_FULL_PROJECTION = {
    "_id": 1, "name": 1, "description": 1, "owner_id": 1, "logo_url": 1,
    "miembros": 1, "salas_ids": 1, "public": 1, "tags": 1, "stats": 1,
    "created_at": 1, "updated_at": 1,
}

_PUBLIC_PROJECTION = {
    "_id": 1, "name": 1, "description": 1, "owner_id": 1, "logo_url": 1,
    "public": 1, "tags": 1, "stats": 1, "created_at": 1,
}


# ---------------------------------------------------------------------------
# Startup — índices
# ---------------------------------------------------------------------------

async def ensure_group_indexes() -> None:
    col = get_grupos_collection()
    await col.create_index([("owner_id", ASCENDING)], name="grupo_owner", background=True)
    await col.create_index(
        [("public", ASCENDING), ("created_at", DESCENDING)],
        name="grupo_public_created", background=True,
    )
    await col.create_index(
        [("name", TEXT), ("tags", TEXT)],
        name="grupo_text_search",
        background=True,
    )
    await col.create_index(
        [("miembros.rider_id", ASCENDING)],
        name="grupo_miembros_rider", background=True,
    )
    logger.info("Índices de grupos verificados")


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


async def _get_grupo_raw(grupo_id: str) -> dict:
    col = get_grupos_collection()
    doc = await col.find_one({"_id": _oid(grupo_id, "ID de grupo")}, _FULL_PROJECTION)
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Grupo no encontrado")
    return _serialize(doc)


def _require_admin(grupo: dict, rider_id: str) -> None:
    for m in grupo.get("miembros", []):
        if m["rider_id"] == rider_id and m["role"] == "admin":
            return
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Solo admins pueden realizar esta acción")


def _is_member(grupo: dict, rider_id: str) -> bool:
    return any(m["rider_id"] == rider_id for m in grupo.get("miembros", []))


def _configure_cloudinary() -> None:
    cloudinary.config(
        cloud_name=settings.CLOUDINARY_CLOUD_NAME,
        api_key=settings.CLOUDINARY_API_KEY,
        api_secret=settings.CLOUDINARY_API_SECRET,
    )


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------

async def create_grupo(
    owner_id: str,
    display_name: str,
    avatar_url: Optional[str],
    data: GrupoCreate,
) -> dict:
    col = get_grupos_collection()
    now = datetime.utcnow()
    doc = {
        "name": data.name,
        "description": data.description,
        "owner_id": owner_id,
        "logo_url": None,
        "miembros": [{
            "rider_id": owner_id,
            "display_name": display_name,
            "avatar_url": avatar_url,
            "role": "admin",
            "joined_at": now,
        }],
        "salas_ids": [],
        "public": data.public,
        "tags": data.tags,
        "stats": {"km_total": 0.0, "amarres_count": 0, "riders_count": 1},
        "created_at": now,
        "updated_at": None,
    }
    result = await col.insert_one(doc)
    doc["_id"] = str(result.inserted_id)
    return doc


async def get_grupo(grupo_id: str) -> dict:
    return await _get_grupo_raw(grupo_id)


async def update_grupo(grupo_id: str, rider_id: str, data: GrupoUpdate) -> dict:
    grupo = await _get_grupo_raw(grupo_id)
    _require_admin(grupo, rider_id)

    patch = data.model_dump(exclude_none=True)
    if not patch:
        return grupo

    patch["updated_at"] = datetime.utcnow()
    col = get_grupos_collection()
    result = await col.find_one_and_update(
        {"_id": _oid(grupo_id)},
        {"$set": patch},
        projection=_FULL_PROJECTION,
        return_document=True,
    )
    return _serialize(result)


async def delete_grupo(grupo_id: str, rider_id: str) -> dict:
    grupo = await _get_grupo_raw(grupo_id)
    if grupo["owner_id"] != rider_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Solo el creador puede eliminar el grupo")
    col = get_grupos_collection()
    await col.delete_one({"_id": _oid(grupo_id)})
    return {"status": "ok", "detail": "Grupo eliminado"}


# ---------------------------------------------------------------------------
# Logo
# ---------------------------------------------------------------------------

async def upload_logo(grupo_id: str, rider_id: str, file: UploadFile) -> dict:
    grupo = await _get_grupo_raw(grupo_id)
    _require_admin(grupo, rider_id)

    if file.content_type not in _ALLOWED_MIME:
        raise HTTPException(status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail="Formato no permitido")
    data = await file.read()
    if len(data) > _MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="Máximo 5 MB")

    _configure_cloudinary()

    def _do_upload():
        return cloudinary.uploader.upload(
            data,
            folder=f"noray4/grupos/{grupo_id}",
            resource_type="image",
            eager=[{"width": 400, "height": 400, "crop": "fill", "fetch_format": "auto"}],
            eager_async=False,
        )

    try:
        result = await asyncio.to_thread(_do_upload)
    except Exception as exc:
        logger.error("Cloudinary logo upload error: %s", exc)
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Error al subir el logo")

    eager = result.get("eager", [])
    logo_url = eager[0]["secure_url"] if eager else result["secure_url"]

    col = get_grupos_collection()
    updated = await col.find_one_and_update(
        {"_id": _oid(grupo_id)},
        {"$set": {"logo_url": logo_url, "updated_at": datetime.utcnow()}},
        projection=_FULL_PROJECTION,
        return_document=True,
    )
    return _serialize(updated)


# ---------------------------------------------------------------------------
# Membresía
# ---------------------------------------------------------------------------

async def join_grupo(
    grupo_id: str,
    rider_id: str,
    display_name: str,
    avatar_url: Optional[str],
) -> dict:
    grupo = await _get_grupo_raw(grupo_id)

    if not grupo["public"]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Solo se puede unir a grupos públicos")

    if _is_member(grupo, rider_id):
        return grupo  # idempotente

    new_member = {
        "rider_id": rider_id,
        "display_name": display_name,
        "avatar_url": avatar_url,
        "role": "rider",
        "joined_at": datetime.utcnow(),
    }
    col = get_grupos_collection()
    result = await col.find_one_and_update(
        {"_id": _oid(grupo_id)},
        {
            "$push": {"miembros": new_member},
            "$inc": {"stats.riders_count": 1},
            "$set": {"updated_at": datetime.utcnow()},
        },
        projection=_FULL_PROJECTION,
        return_document=True,
    )
    return _serialize(result)


async def leave_grupo(grupo_id: str, rider_id: str) -> dict:
    grupo = await _get_grupo_raw(grupo_id)

    if grupo["owner_id"] == rider_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El owner no puede salir — transfiere la propiedad primero",
        )
    if not _is_member(grupo, rider_id):
        return {"status": "ok", "detail": "No eras miembro del grupo"}

    col = get_grupos_collection()
    await col.update_one(
        {"_id": _oid(grupo_id)},
        {
            "$pull": {"miembros": {"rider_id": rider_id}},
            "$inc": {"stats.riders_count": -1},
            "$set": {"updated_at": datetime.utcnow()},
        },
    )
    return {"status": "ok", "detail": "Saliste del grupo"}


async def kick_member(grupo_id: str, admin_rider_id: str, target_rider_id: str) -> dict:
    grupo = await _get_grupo_raw(grupo_id)
    _require_admin(grupo, admin_rider_id)

    if grupo["owner_id"] == target_rider_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No se puede expulsar al owner")
    if not _is_member(grupo, target_rider_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="El rider no es miembro del grupo")

    col = get_grupos_collection()
    result = await col.find_one_and_update(
        {"_id": _oid(grupo_id)},
        {
            "$pull": {"miembros": {"rider_id": target_rider_id}},
            "$inc": {"stats.riders_count": -1},
            "$set": {"updated_at": datetime.utcnow()},
        },
        projection=_FULL_PROJECTION,
        return_document=True,
    )
    return _serialize(result)


async def change_role(grupo_id: str, owner_rider_id: str, target_rider_id: str, new_role: str) -> dict:
    grupo = await _get_grupo_raw(grupo_id)

    if grupo["owner_id"] != owner_rider_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Solo el owner puede cambiar roles")
    if not _is_member(grupo, target_rider_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="El rider no es miembro del grupo")

    col = get_grupos_collection()
    result = await col.find_one_and_update(
        {"_id": _oid(grupo_id), "miembros.rider_id": target_rider_id},
        {
            "$set": {
                "miembros.$.role": new_role,
                "updated_at": datetime.utcnow(),
            }
        },
        projection=_FULL_PROJECTION,
        return_document=True,
    )
    return _serialize(result)


# ---------------------------------------------------------------------------
# Búsqueda y listados
# ---------------------------------------------------------------------------

async def search_grupos(query: str, skip: int = 0, limit: int = 20) -> dict:
    limit = min(limit, 50)
    col = get_grupos_collection()
    f: Dict[str, Any] = {"public": True}
    if query.strip():
        f["$text"] = {"$search": query}

    total, docs = await asyncio.gather(
        col.count_documents(f),
        _fetch(col, f, _PUBLIC_PROJECTION, skip, limit),
    )
    return {"items": docs, "total": total, "skip": skip, "limit": limit, "has_more": (skip + limit) < total}


async def get_mis_grupos(rider_id: str, skip: int = 0, limit: int = 20) -> dict:
    limit = min(limit, 50)
    col = get_grupos_collection()
    f = {"miembros.rider_id": rider_id}
    total, docs = await asyncio.gather(
        col.count_documents(f),
        _fetch(col, f, _FULL_PROJECTION, skip, limit),
    )
    return {"items": docs, "total": total, "skip": skip, "limit": limit, "has_more": (skip + limit) < total}


async def get_miembros_grupo(grupo_id: str) -> list:
    grupo = await _get_grupo_raw(grupo_id)
    return grupo.get("miembros", [])


async def _fetch(col, query: dict, projection: dict, skip: int, limit: int) -> list:
    cursor = col.find(query, projection).sort("created_at", DESCENDING).skip(skip).limit(limit)
    return [_serialize(doc) async for doc in cursor]


# ---------------------------------------------------------------------------
# Salas del grupo
# ---------------------------------------------------------------------------

async def add_sala_to_grupo(grupo_id: str, sala_id: str, rider_id: str) -> dict:
    grupo = await _get_grupo_raw(grupo_id)
    if not _is_member(grupo, rider_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Solo miembros pueden vincular salas")

    col = get_grupos_collection()
    await col.update_one(
        {"_id": _oid(grupo_id)},
        {"$addToSet": {"salas_ids": sala_id}, "$set": {"updated_at": datetime.utcnow()}},
    )
    return {"status": "ok", "sala_id": sala_id, "grupo_id": grupo_id}


async def get_salas_grupo(grupo_id: str, rider_id: str) -> list:
    grupo = await _get_grupo_raw(grupo_id)
    if not _is_member(grupo, rider_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Solo miembros pueden ver las salas")

    salas_ids = grupo.get("salas_ids", [])
    if not salas_ids:
        return []

    col = get_salas_collection()
    oids = [_oid(sid) for sid in salas_ids if ObjectId.is_valid(sid)]
    projection = {"_id": 1, "name": 1, "status": 1, "created_at": 1, "closed_at": 1, "owner_id": 1}
    cursor = col.find({"_id": {"$in": oids}}, projection)
    docs = []
    async for doc in cursor:
        doc["_id"] = str(doc["_id"])
        docs.append(doc)
    return docs


# ---------------------------------------------------------------------------
# Stats — recalculado bajo demanda
# ---------------------------------------------------------------------------

async def recalc_stats(grupo_id: str, rider_id: str) -> dict:
    grupo = await _get_grupo_raw(grupo_id)
    _require_admin(grupo, rider_id)

    rider_ids = [m["rider_id"] for m in grupo.get("miembros", [])]
    riders_count = len(rider_ids)

    # Aggregation en amarres — suma km y count de todos los riders del grupo
    amarres_col = get_amarres_collection()
    pipeline = [
        {"$match": {"riders": {"$in": rider_ids}}},
        {"$group": {"_id": None, "amarres_count": {"$sum": 1}, "km_total": {"$sum": "$km_total"}}},
    ]
    agg = await amarres_col.aggregate(pipeline).to_list(1)
    amarres_count = agg[0]["amarres_count"] if agg else 0
    km_total = round(agg[0]["km_total"], 1) if agg else 0.0

    new_stats = {"km_total": km_total, "amarres_count": amarres_count, "riders_count": riders_count}

    col = get_grupos_collection()
    await col.update_one(
        {"_id": _oid(grupo_id)},
        {"$set": {"stats": new_stats, "updated_at": datetime.utcnow()}},
    )
    return {"status": "ok", "grupo_id": grupo_id, "stats": new_stats}


# ---------------------------------------------------------------------------
# Conteo de grupos para MS-Riders stats
# ---------------------------------------------------------------------------

async def get_rider_group_count(rider_id: str) -> int:
    col = get_grupos_collection()
    return await col.count_documents({"miembros.rider_id": rider_id})
