from typing import Optional

from fastapi import APIRouter, Body, Depends, Query, status

from shared.dependencies import get_current_rider
from ms_salas.schemas import JoinRequest, MiembroOut, QROut, SalaCreate, SalaOut, SalaUpdate
from ms_salas import service

router = APIRouter(prefix="/salas", tags=["salas"])


@router.get(
    "",
    response_model=list[SalaOut],
    summary="Listar salas activas",
    description=(
        "Retorna la lista paginada de salas con status active, ordenadas por fecha de creación "
        "descendente. Soporta parámetros skip y limit para paginación."
    ),
)
async def list_salas(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    rider: dict = Depends(get_current_rider),
):
    return await service.get_salas_activas(skip=skip, limit=limit)


@router.post(
    "",
    response_model=SalaOut,
    status_code=status.HTTP_201_CREATED,
    summary="Crear nueva sala",
    description=(
        "Crea una sala de ruta con nombre, descripción y privacidad configurables. El rider autenticado "
        "se convierte automáticamente en administrador. Genera QR token y link de invitación."
    ),
)
async def create_sala(body: SalaCreate, rider: dict = Depends(get_current_rider)):
    return await service.create_sala(
        owner_rider_id=rider["_id"],
        owner_display_name=rider["display_name"],
        data=body,
    )


@router.get(
    "/{sala_id}",
    response_model=SalaOut,
    summary="Obtener detalle de sala",
    description=(
        "Retorna todos los datos de una sala incluyendo lista de miembros, estado y metadatos. "
        "Lanza 404 si la sala no existe."
    ),
)
async def get_sala(sala_id: str, rider: dict = Depends(get_current_rider)):
    return await service.get_sala_by_id(sala_id)


@router.put(
    "/{sala_id}",
    response_model=SalaOut,
    summary="Actualizar sala",
    description=(
        "Actualiza nombre, descripción o privacidad de la sala. Solo el miembro con rol admin puede "
        "realizar esta operación. Lanza 403 si el rider autenticado no es administrador."
    ),
)
async def update_sala(
    sala_id: str,
    body: SalaUpdate,
    rider: dict = Depends(get_current_rider),
):
    return await service.update_sala(sala_id, rider["_id"], body)


@router.post(
    "/{sala_id}/join",
    response_model=SalaOut,
    summary="Unirse a una sala",
    description=(
        "Agrega al rider autenticado como miembro con rol rider. Para salas privadas requiere "
        "qr_token válido en el body. Operación idempotente: si ya es miembro retorna la sala sin error."
    ),
)
async def join_sala(
    sala_id: str,
    body: Optional[JoinRequest] = Body(default=None),
    rider: dict = Depends(get_current_rider),
):
    return await service.join_sala(
        sala_id=sala_id,
        rider_id=rider["_id"],
        display_name=rider["display_name"],
        qr_token=body.qr_token if body else None,
    )


@router.post(
    "/{sala_id}/close",
    response_model=SalaOut,
    summary="Cerrar sala",
    description=(
        "Cambia el status de la sala a closed y registra la fecha de cierre. Solo el administrador "
        "puede cerrar la sala. En Sprint 2 disparará la creación automática del amarre."
    ),
)
async def close_sala(sala_id: str, rider: dict = Depends(get_current_rider)):
    return await service.close_sala(sala_id, rider["_id"])


@router.get(
    "/{sala_id}/qr",
    response_model=QROut,
    summary="Obtener QR de invitación",
    description=(
        "Retorna el token QR y el link de invitación de la sala. Solo accesible para miembros "
        "actuales. Lanza 403 si el rider autenticado no pertenece a la sala."
    ),
)
async def get_qr(sala_id: str, rider: dict = Depends(get_current_rider)):
    return await service.get_qr(sala_id, rider["_id"])


@router.get(
    "/{sala_id}/miembros",
    response_model=list[MiembroOut],
    summary="Listar miembros de la sala",
    description=(
        "Retorna la lista completa de miembros de la sala con su rol y fecha de ingreso."
    ),
)
async def get_miembros(sala_id: str, rider: dict = Depends(get_current_rider)):
    return await service.get_miembros(sala_id)
