from typing import List

from fastapi import APIRouter, Depends, status

from shared.dependencies import get_current_rider
from ms_voice.schemas import CanalCreate, CanalOut, PTTRequest, PTTState, VozStatusOut, WebRTCSignal
from ms_voice import service

router = APIRouter(prefix="/voice", tags=["voice"])


@router.post(
    "/{sala_id}/canales",
    response_model=CanalOut,
    status_code=status.HTTP_201_CREATED,
    summary="Crear canal de voz",
    description=(
        "Crea un canal de voz custom en la sala. Los canales general, lideres y emergencia "
        "se crean automáticamente al abrir la sala. Requiere membresía activa."
    ),
)
async def create_canal(
    sala_id: str,
    body: CanalCreate,
    rider: dict = Depends(get_current_rider),
):
    return await service.create_canal(sala_id, rider["_id"], body)


@router.get(
    "/{sala_id}/canales",
    response_model=List[CanalOut],
    summary="Listar canales de voz",
    description=(
        "Retorna los canales de voz activos de la sala. Incluye los canales default "
        "(general, lideres, emergencia) y cualquier canal custom creado. Requiere membresía."
    ),
)
async def get_canales(sala_id: str, rider: dict = Depends(get_current_rider)):
    return await service.get_canales(sala_id, rider["_id"])


@router.post(
    "/{sala_id}/ptt",
    response_model=PTTState,
    summary="Tomar o soltar turno PTT",
    description=(
        "action=start: solicita el turno de voz en el canal. Si otro rider está hablando "
        "retorna 409 con el nombre del speaker actual. "
        "action=stop: suelta el turno. Idempotente si el rider no era el speaker. "
        "Publica evento al topic MQTT noray4/{sala_id}/voz fire-and-forget."
    ),
)
async def ptt_action(
    sala_id: str,
    body: PTTRequest,
    rider: dict = Depends(get_current_rider),
):
    return await service.ptt_action(sala_id, rider["_id"], rider["display_name"], body)


@router.get(
    "/{sala_id}/status",
    response_model=List[VozStatusOut],
    summary="Estado de voz de la sala",
    description=(
        "Retorna el estado PTT actual de todos los canales activos de la sala: "
        "quién está hablando, participantes por canal y flag is_speaking. "
        "Consulta O(canales) sobre el PTTStore en memoria — no toca MongoDB."
    ),
)
async def get_voz_status(sala_id: str, rider: dict = Depends(get_current_rider)):
    return await service.get_voz_status(sala_id, rider["_id"])


@router.post(
    "/{sala_id}/signal",
    summary="Enviar señal WebRTC",
    description=(
        "Publica una señal de señalización WebRTC (offer, answer, ice-candidate) al broker MQTT. "
        "El cliente destino filtra por target_rider_id en el topic noray4/{sala_id}/voz. "
        "El audio viaja P2P — el servidor solo retransmite señales de control."
    ),
)
async def send_signal(
    sala_id: str,
    body: WebRTCSignal,
    rider: dict = Depends(get_current_rider),
):
    return await service.send_signal(sala_id, rider["_id"], body)


@router.post(
    "/{sala_id}/force-release/{canal_id}",
    summary="Forzar liberación del turno PTT",
    description=(
        "Admin únicamente: libera el turno PTT de cualquier rider en el canal. "
        "Publica evento ptt_force_release al canal MQTT. Lanza 403 si el rider no es admin."
    ),
)
async def force_release(
    sala_id: str,
    canal_id: str,
    rider: dict = Depends(get_current_rider),
):
    return await service.force_release(sala_id, rider["_id"], canal_id)
