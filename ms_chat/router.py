from fastapi import APIRouter, Depends, Query, UploadFile, status

from shared.dependencies import get_current_rider
from ms_chat.schemas import (
    ACKRequest,
    MensajeCreate,
    MensajeOut,
    MensajeUpdate,
    PaginatedMensajes,
    UploadResponse,
)
from ms_chat import service

router = APIRouter(prefix="/chat", tags=["chat"])


@router.get(
    "/{sala_id}/mensajes",
    response_model=PaginatedMensajes,
    summary="Obtener mensajes de la sala",
    description=(
        "Retorna mensajes paginados en orden cronológico. Cursor DESC en DB, revertido antes de "
        "retornar. Excluye mensajes eliminados. Máximo 100 por request. Requiere ser miembro."
    ),
)
async def get_mensajes(
    sala_id: str,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
    rider: dict = Depends(get_current_rider),
):
    return await service.get_mensajes(sala_id, skip=skip, limit=limit)


@router.post(
    "/{sala_id}/mensajes",
    response_model=MensajeOut,
    status_code=status.HTTP_201_CREATED,
    summary="Enviar mensaje",
    description=(
        "Persiste el mensaje en MongoDB y lo publica al topic MQTT noray4/{sala_id}/chat. "
        "Requiere membresía activa. Para type=text: content obligatorio. Para type=coords: coords obligatorio."
    ),
)
async def create_mensaje(
    sala_id: str,
    body: MensajeCreate,
    rider: dict = Depends(get_current_rider),
):
    return await service.create_mensaje(
        sala_id=sala_id,
        rider_id=rider["_id"],
        display_name=rider["display_name"],
        data=body,
    )


@router.put(
    "/{sala_id}/mensajes/{mensaje_id}",
    response_model=MensajeOut,
    summary="Editar mensaje",
    description=(
        "Actualiza el contenido del mensaje. Solo el autor puede editar. "
        "Solo mensajes de tipo text son editables. Marca edited=True y registra updated_at."
    ),
)
async def edit_mensaje(
    sala_id: str,
    mensaje_id: str,
    body: MensajeUpdate,
    rider: dict = Depends(get_current_rider),
):
    return await service.edit_mensaje(mensaje_id, rider["_id"], body.content)


@router.delete(
    "/{sala_id}/mensajes/{mensaje_id}",
    summary="Eliminar mensaje (soft delete)",
    description=(
        "Marca el mensaje como deleted=True sin eliminarlo físicamente. "
        "El autor o el admin de la sala pueden borrar. Publica evento al canal MQTT."
    ),
)
async def delete_mensaje(
    sala_id: str,
    mensaje_id: str,
    rider: dict = Depends(get_current_rider),
):
    return await service.delete_mensaje(mensaje_id, rider["_id"])


@router.post(
    "/{sala_id}/mensajes/{mensaje_id}/ack",
    summary="Confirmar entrega de mensaje",
    description=(
        "Agrega el rider_id autenticado a delivered_to del mensaje usando $addToSet. "
        "Idempotente: si ya había confirmado, retorna 200 sin modificar el documento."
    ),
)
async def ack_mensaje(
    sala_id: str,
    mensaje_id: str,
    rider: dict = Depends(get_current_rider),
):
    return await service.ack_mensaje(mensaje_id, rider["_id"])


@router.post(
    "/{sala_id}/upload",
    response_model=UploadResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Subir archivo multimedia",
    description=(
        "Sube una imagen a Cloudinary en la carpeta noray4/salas/{sala_id}/. "
        "Genera thumbnail automático (width=400). Acepta: image/jpeg, image/png, image/webp. "
        "Tamaño máximo: 10 MB. Retorna media_url, thumb_url y public_id."
    ),
)
async def upload_media(
    sala_id: str,
    file: UploadFile,
    rider: dict = Depends(get_current_rider),
):
    return await service.upload_media(sala_id, rider["_id"], file)
