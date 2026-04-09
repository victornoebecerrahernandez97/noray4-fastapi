from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, status

from shared.database import get_salas_collection
from shared.dependencies import get_current_rider
from ms_realtime.mqtt_client import TOPIC_EVENTOS, TOPIC_UBICACION, mqtt_gateway
from ms_realtime.schemas import EventoPayload, UbicacionPayload

router = APIRouter(prefix="/realtime", tags=["realtime"])


# ---------------------------------------------------------------------------
# Helper — membresía y admin
# ---------------------------------------------------------------------------

async def _get_sala_or_404(sala_id: str) -> dict:
    try:
        oid = ObjectId(sala_id)
    except Exception:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="ID de sala inválido")
    col = get_salas_collection()
    sala = await col.find_one({"_id": oid})
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


def _require_admin(sala: dict, rider_id: str) -> None:
    if sala["owner_id"] != rider_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Solo el admin puede publicar eventos",
        )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post(
    "/{sala_id}/ubicacion",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Publicar ubicación GPS",
    description=(
        "Publica la ubicación GPS del rider al topic MQTT noray4/{sala_id}/ubicacion. "
        "Requiere ser miembro activo de la sala. Lanza 403 si el rider no pertenece a la sala."
    ),
)
async def publish_ubicacion(
    sala_id: str,
    body: UbicacionPayload,
    rider: dict = Depends(get_current_rider),
):
    sala = await _get_sala_or_404(sala_id)
    _require_member(sala, rider["_id"])
    # Sobrescribir rider_id con el autenticado para evitar suplantación
    payload = body.model_dump()
    payload["rider_id"] = rider["_id"]
    mqtt_gateway.publish(TOPIC_UBICACION.format(sala_id=sala_id), payload)


@router.post(
    "/{sala_id}/evento",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Publicar evento de sala",
    description=(
        "Publica un evento al topic MQTT noray4/{sala_id}/eventos. "
        "Solo el administrador de la sala puede publicar eventos. Lanza 403 en caso contrario."
    ),
)
async def publish_evento(
    sala_id: str,
    body: EventoPayload,
    rider: dict = Depends(get_current_rider),
):
    sala = await _get_sala_or_404(sala_id)
    _require_member(sala, rider["_id"])
    _require_admin(sala, rider["_id"])
    mqtt_gateway.publish(TOPIC_EVENTOS.format(sala_id=sala_id), body.model_dump(mode="json"))


@router.get(
    "/{sala_id}/status",
    summary="Estado de conexión MQTT de la sala",
    description=(
        "Retorna el estado de conexión del gateway MQTT y la lista de miembros de la sala. "
        "Requiere ser miembro. Los riders actualmente online se determinan via presencia MQTT."
    ),
)
async def get_status(
    sala_id: str,
    rider: dict = Depends(get_current_rider),
):
    sala = await _get_sala_or_404(sala_id)
    _require_member(sala, rider["_id"])
    return {
        "status": "ok",
        "data": {
            "mqtt_connected": mqtt_gateway.is_connected,
            "sala_id": sala_id,
            "miembros_total": len(sala.get("miembros", [])),
        },
    }
