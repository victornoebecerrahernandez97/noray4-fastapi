import logging
from datetime import datetime
from typing import List

from bson import ObjectId
from fastapi import HTTPException, status
from pymongo import ASCENDING

from shared.database import get_canales_collection, get_salas_collection
from ms_voice.ptt_store import PTTConflictError, ptt_store
from ms_voice.schemas import CanalCreate, PTTRequest, PTTState, VozStatusOut, WebRTCSignal

logger = logging.getLogger("noray4.voice")

_CANAL_PROJECTION = {"_id": 1, "sala_id": 1, "name": 1, "activo": 1, "created_by": 1, "created_at": 1}
_DEFAULT_CANALES = ["general", "lideres", "emergencia"]


# ---------------------------------------------------------------------------
# Startup — índices
# ---------------------------------------------------------------------------

async def ensure_voice_indexes() -> None:
    col = get_canales_collection()
    await col.create_index([("sala_id", ASCENDING)], name="canal_sala_id", background=True)
    await col.create_index(
        [("sala_id", ASCENDING), ("activo", ASCENDING)],
        name="canal_sala_activo", background=True,
    )
    logger.info("Índices de canales de voz verificados")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _serialize(doc: dict) -> dict:
    doc["_id"] = str(doc["_id"])
    return doc


async def _require_member(sala_id: str, rider_id: str) -> dict:
    try:
        oid = ObjectId(sala_id)
    except Exception:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="ID de sala inválido")
    salas = get_salas_collection()
    sala = await salas.find_one({"_id": oid})
    if not sala:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sala no encontrada")
    if not any(m["rider_id"] == rider_id for m in sala.get("miembros", [])):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No eres miembro de esta sala")
    sala["_id"] = str(sala["_id"])
    return sala


def _publish_voz(sala_id: str, payload: dict) -> None:
    """Fire-and-forget MQTT publish al topic de voz."""
    try:
        from ms_realtime.mqtt_client import mqtt_gateway
        mqtt_gateway.publish(f"noray4/{sala_id}/voz", payload)
    except Exception as exc:
        logger.debug("MQTT publish (voz) ignorado: %s", exc)


# ---------------------------------------------------------------------------
# Canales
# ---------------------------------------------------------------------------

async def create_canal(sala_id: str, rider_id: str, data: CanalCreate) -> dict:
    await _require_member(sala_id, rider_id)
    col = get_canales_collection()
    doc = {
        "sala_id": sala_id,
        "name": data.name,
        "created_by": rider_id,
        "activo": True,
        "created_at": datetime.utcnow(),
    }
    result = await col.insert_one(doc)
    doc["_id"] = str(result.inserted_id)
    return doc


async def create_default_canales(sala_id: str, rider_id: str) -> None:
    """Crea los 3 canales default al abrir una sala. Llamado desde ms_salas.create_sala."""
    col = get_canales_collection()
    now = datetime.utcnow()
    docs = [
        {"sala_id": sala_id, "name": name, "created_by": rider_id, "activo": True, "created_at": now}
        for name in _DEFAULT_CANALES
    ]
    await col.insert_many(docs)
    logger.info("Canales default creados para sala %s", sala_id)


async def get_canales(sala_id: str, rider_id: str) -> List[dict]:
    await _require_member(sala_id, rider_id)
    col = get_canales_collection()
    cursor = col.find({"sala_id": sala_id, "activo": True}, _CANAL_PROJECTION)
    return [_serialize(doc) async for doc in cursor]


# ---------------------------------------------------------------------------
# PTT
# ---------------------------------------------------------------------------

async def ptt_action(
    sala_id: str,
    rider_id: str,
    display_name: str,
    data: PTTRequest,
) -> PTTState:
    await _require_member(sala_id, rider_id)

    if data.action == "start":
        try:
            state = ptt_store.set_speaking(data.canal_id, sala_id, rider_id, display_name)
        except PTTConflictError as exc:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Canal ocupado — {exc.current_speaker_name} está hablando",
            )
        _publish_voz(sala_id, {
            "type": "ptt_start",
            "canal_id": data.canal_id,
            "speaker_id": rider_id,
            "speaker_name": display_name,
            "timestamp": state.timestamp.isoformat(),
        })
    else:
        state = ptt_store.release_speaking(data.canal_id, sala_id, rider_id)
        _publish_voz(sala_id, {
            "type": "ptt_stop",
            "canal_id": data.canal_id,
            "speaker_id": rider_id,
            "timestamp": state.timestamp.isoformat(),
        })

    return state


async def get_voz_status(sala_id: str, rider_id: str) -> List[VozStatusOut]:
    await _require_member(sala_id, rider_id)
    col = get_canales_collection()
    cursor = col.find({"sala_id": sala_id, "activo": True}, _CANAL_PROJECTION)

    result = []
    async for canal in cursor:
        canal_id = str(canal["_id"])
        state = ptt_store.get_state(canal_id)
        result.append(VozStatusOut(
            canal_id=canal_id,
            canal_name=canal["name"],
            is_speaking=state.is_speaking if state else False,
            speaker_id=state.speaker_id if state else None,
            speaker_name=state.speaker_name if state else None,
            participants=ptt_store.get_participants(canal_id),
        ))
    return result


# ---------------------------------------------------------------------------
# WebRTC Signaling
# ---------------------------------------------------------------------------

async def send_signal(sala_id: str, rider_id: str, data: WebRTCSignal) -> dict:
    await _require_member(sala_id, rider_id)
    _publish_voz(sala_id, {
        "type": data.type,
        "from_rider_id": rider_id,
        "target_rider_id": data.target_rider_id,
        "canal_id": data.canal_id,
        "payload": data.payload,
    })
    return {"status": "sent"}


async def force_release(sala_id: str, rider_id: str, canal_id: str) -> dict:
    sala = await _require_member(sala_id, rider_id)
    if sala["owner_id"] != rider_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Solo el admin puede forzar liberación")
    ptt_store.force_release(canal_id)
    _publish_voz(sala_id, {
        "type": "ptt_force_release",
        "canal_id": canal_id,
        "by_rider_id": rider_id,
        "timestamp": datetime.utcnow().isoformat(),
    })
    return {"status": "released", "canal_id": canal_id}
