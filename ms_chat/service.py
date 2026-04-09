"""
ms_chat/service.py — Lógica de negocio para mensajería en sala.

Decisiones de escalabilidad:
- Proyección en todas las queries: solo los campos necesarios
- Índices compuestos definidos en ensure_chat_indexes() (llamado en lifespan)
- MQTT publish es fire-and-forget: no bloquea la respuesta HTTP
- Cloudinary upload en asyncio.to_thread(): no bloquea el event loop
- Hard limit de 100 mensajes por request
- Soft delete: never physically removes documents
"""
import asyncio
import logging
from datetime import datetime
from typing import Any, Dict

import cloudinary
import cloudinary.uploader
from bson import ObjectId
from fastapi import HTTPException, UploadFile, status
from pymongo import ASCENDING, DESCENDING

from shared.config import settings
from shared.database import get_mensajes_collection, get_salas_collection
from ms_chat.schemas import MensajeCreate, PaginatedMensajes

logger = logging.getLogger("noray4.chat")

# Tipos de contenido permitidos para upload
_ALLOWED_MIME = {"image/jpeg", "image/png", "image/webp"}
_MAX_UPLOAD_BYTES = 10 * 1024 * 1024  # 10 MB

# Proyección — nunca traer campos que no usa MensajeOut
_PROJECTION = {
    "_id": 1,
    "sala_id": 1,
    "rider_id": 1,
    "display_name": 1,
    "type": 1,
    "content": 1,
    "media_url": 1,
    "media_thumb_url": 1,
    "coords": 1,
    "file_meta": 1,
    "reply_to": 1,
    "edited": 1,
    "deleted": 1,
    "delivered_to": 1,
    "created_at": 1,
    "updated_at": 1,
}


# ---------------------------------------------------------------------------
# Startup — índices
# ---------------------------------------------------------------------------

async def ensure_chat_indexes() -> None:
    """Crea índices de la colección mensajes. Idempotente — safe en cada startup."""
    col = get_mensajes_collection()
    await col.create_index(
        [("sala_id", ASCENDING), ("created_at", DESCENDING)],
        name="sala_created_at",
        background=True,
    )
    await col.create_index(
        [("rider_id", ASCENDING)],
        name="rider_id",
        background=True,
    )
    await col.create_index(
        [("sala_id", ASCENDING), ("type", ASCENDING)],
        name="sala_type",
        background=True,
    )
    logger.info("Índices de mensajes verificados")


# ---------------------------------------------------------------------------
# Helpers internos
# ---------------------------------------------------------------------------

def _serialize(doc: dict) -> dict:
    doc["_id"] = str(doc["_id"])
    return doc


def _oid(value: str, label: str = "ID") -> ObjectId:
    try:
        return ObjectId(value)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"{label} inválido",
        )


async def _get_sala(sala_id: str) -> dict:
    col = get_salas_collection()
    sala = await col.find_one({"_id": _oid(sala_id, "ID de sala")})
    if not sala:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sala no encontrada")
    sala["_id"] = str(sala["_id"])
    return sala


def _require_member(sala: dict, rider_id: str) -> None:
    if not any(m["rider_id"] == rider_id for m in sala.get("miembros", [])):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No eres miembro de esta sala",
        )


async def _get_mensaje(mensaje_id: str) -> dict:
    col = get_mensajes_collection()
    doc = await col.find_one(
        {"_id": _oid(mensaje_id, "ID de mensaje"), "deleted": False},
        _PROJECTION,
    )
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Mensaje no encontrado",
        )
    return _serialize(doc)


def _publish_chat(sala_id: str, payload: Dict[str, Any]) -> None:
    """Fire-and-forget MQTT publish — no lanza excepciones."""
    try:
        from ms_realtime.mqtt_client import mqtt_gateway
        mqtt_gateway.publish(f"noray4/{sala_id}/chat", payload)
    except Exception as exc:
        logger.debug("MQTT publish error (ignorado): %s", exc)


# ---------------------------------------------------------------------------
# Paginación
# ---------------------------------------------------------------------------

async def get_mensajes(sala_id: str, skip: int = 0, limit: int = 50) -> dict:
    limit = min(limit, 100)  # hard cap

    col = get_mensajes_collection()
    base_filter = {"sala_id": sala_id, "deleted": False}

    # Count y cursor en paralelo
    total, cursor_docs = await asyncio.gather(
        col.count_documents(base_filter),
        _fetch_mensajes_cursor(col, base_filter, skip, limit),
    )

    has_more = (skip + limit) < total
    return {
        "items": cursor_docs,
        "total": total,
        "skip": skip,
        "limit": limit,
        "has_more": has_more,
    }


async def _fetch_mensajes_cursor(col, base_filter: dict, skip: int, limit: int) -> list:
    cursor = (
        col.find(base_filter, _PROJECTION)
        .sort("created_at", DESCENDING)
        .skip(skip)
        .limit(limit)
    )
    docs = []
    async for doc in cursor:
        docs.append(_serialize(doc))
    # Revertir a orden cronológico para el cliente
    docs.reverse()
    return docs


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------

async def create_mensaje(
    sala_id: str,
    rider_id: str,
    display_name: str,
    data: MensajeCreate,
) -> dict:
    sala = await _get_sala(sala_id)

    if sala.get("status") == "closed":
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail="La sala está cerrada",
        )
    _require_member(sala, rider_id)

    now = datetime.utcnow()
    doc: Dict[str, Any] = {
        "sala_id": sala_id,
        "rider_id": rider_id,
        "display_name": display_name,
        "type": data.type,
        "content": data.content,
        "media_url": None,
        "media_thumb_url": None,
        "coords": data.coords,
        "file_meta": data.file_meta,
        "reply_to": data.reply_to,
        "edited": False,
        "deleted": False,
        "delivered_to": [],
        "created_at": now,
        "updated_at": None,
    }

    col = get_mensajes_collection()
    result = await col.insert_one(doc)
    doc["_id"] = str(result.inserted_id)

    # Publish MQTT fire-and-forget (no bloquea)
    _publish_chat(sala_id, {**doc, "created_at": now.isoformat()})

    return doc


async def edit_mensaje(mensaje_id: str, rider_id: str, content: str) -> dict:
    mensaje = await _get_mensaje(mensaje_id)

    if mensaje["rider_id"] != rider_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Solo el autor puede editar su mensaje",
        )
    if mensaje["type"] != "text":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Solo los mensajes de tipo text son editables",
        )

    now = datetime.utcnow()
    col = get_mensajes_collection()
    result = await col.find_one_and_update(
        {"_id": _oid(mensaje_id)},
        {"$set": {"content": content, "edited": True, "updated_at": now}},
        projection=_PROJECTION,
        return_document=True,
    )
    return _serialize(result)


async def delete_mensaje(mensaje_id: str, rider_id: str) -> dict:
    mensaje = await _get_mensaje(mensaje_id)

    is_author = mensaje["rider_id"] == rider_id

    # Verificar si es admin de la sala (owner_id)
    is_admin = False
    if not is_author:
        sala = await _get_sala(mensaje["sala_id"])
        is_admin = sala.get("owner_id") == rider_id

    if not is_author and not is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Solo el autor o el admin pueden eliminar este mensaje",
        )

    col = get_mensajes_collection()
    await col.update_one(
        {"_id": _oid(mensaje_id)},
        {"$set": {"deleted": True, "updated_at": datetime.utcnow()}},
    )

    # Notificar eliminación al canal MQTT (fire-and-forget)
    _publish_chat(mensaje["sala_id"], {
        "type": "system",
        "event": "mensaje_eliminado",
        "mensaje_id": mensaje_id,
    })

    return {"status": "ok", "detail": "Mensaje eliminado"}


# ---------------------------------------------------------------------------
# ACK de entrega
# ---------------------------------------------------------------------------

async def ack_mensaje(mensaje_id: str, rider_id: str) -> dict:
    col = get_mensajes_collection()
    result = await col.update_one(
        {"_id": _oid(mensaje_id, "ID de mensaje"), "deleted": False},
        {"$addToSet": {"delivered_to": rider_id}},
    )
    if result.matched_count == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Mensaje no encontrado",
        )
    return {"status": "ok", "mensaje_id": mensaje_id}


# ---------------------------------------------------------------------------
# Upload de media (Cloudinary)
# ---------------------------------------------------------------------------

def _configure_cloudinary() -> None:
    cloudinary.config(
        cloud_name=settings.CLOUDINARY_CLOUD_NAME,
        api_key=settings.CLOUDINARY_API_KEY,
        api_secret=settings.CLOUDINARY_API_SECRET,
    )


async def upload_media(sala_id: str, rider_id: str, file: UploadFile) -> dict:
    if file.content_type not in _ALLOWED_MIME:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Formato no permitido. Acepta: {', '.join(_ALLOWED_MIME)}",
        )

    data = await file.read()
    if len(data) > _MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Archivo demasiado grande. Máximo 10 MB.",
        )

    _configure_cloudinary()

    def _do_upload() -> dict:
        return cloudinary.uploader.upload(
            data,
            folder=f"noray4/salas/{sala_id}",
            resource_type="image",
            eager=[{"width": 400, "crop": "scale", "fetch_format": "auto"}],
            eager_async=False,
        )

    try:
        result = await asyncio.to_thread(_do_upload)
    except Exception as exc:
        logger.error("Cloudinary upload error: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Error al subir el archivo. Intenta de nuevo.",
        )

    eager = result.get("eager", [])
    thumb_url = eager[0]["secure_url"] if eager else result["secure_url"]

    return {
        "media_url": result["secure_url"],
        "thumb_url": thumb_url,
        "public_id": result["public_id"],
    }
