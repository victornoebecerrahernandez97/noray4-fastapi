from fastapi import APIRouter, Depends, status

from shared.dependencies import get_current_user
from ms_riders.schemas import MotoUpdate, RiderOut, RiderUpdate, StatsOut
from ms_riders import service

router = APIRouter(prefix="/riders", tags=["riders"])


@router.get(
    "/me",
    response_model=RiderOut,
    summary="Obtener mi perfil de rider",
    description=(
        "Retorna el perfil completo del rider autenticado incluyendo datos de moto, estadísticas y "
        "contadores de seguidores. Lanza 404 si el perfil aún no ha sido creado."
    ),
)
async def get_my_rider(user_id: str = Depends(get_current_user)):
    return await service.get_rider_by_user_id(user_id)


@router.put(
    "/me",
    response_model=RiderOut,
    summary="Actualizar mi perfil",
    description=(
        "Actualiza los campos del perfil del rider autenticado. Todos los campos son opcionales. "
        "Retorna el perfil actualizado. No permite modificar user_id ni timestamps."
    ),
)
async def update_my_rider(body: RiderUpdate, user_id: str = Depends(get_current_user)):
    return await service.update_rider(user_id, body.model_dump(exclude_none=True))


@router.get(
    "/{rider_id}",
    response_model=RiderOut,
    summary="Obtener perfil público de un rider",
    description=(
        "Retorna el perfil público de cualquier rider por su ID. No requiere que sea el usuario "
        "autenticado. Lanza 404 si el rider no existe."
    ),
)
async def get_rider(rider_id: str):
    return await service.get_rider_by_id(rider_id)


@router.post(
    "/me/moto",
    response_model=RiderOut,
    summary="Registrar o actualizar moto",
    description=(
        "Crea o actualiza los datos del vehículo del rider autenticado: modelo, año y kilometraje. "
        "Si ya existe una moto registrada, la sobreescribe."
    ),
)
async def update_my_moto(body: MotoUpdate, user_id: str = Depends(get_current_user)):
    return await service.update_moto(user_id, body.model_dump())


@router.post(
    "/{rider_id}/follow",
    response_model=RiderOut,
    summary="Seguir a un rider",
    description=(
        "Agrega al rider autenticado como seguidor del rider especificado. Operación idempotente: "
        "si ya sigue al rider, retorna 200 sin duplicar. Lanza 404 si el rider objetivo no existe."
    ),
)
async def follow(rider_id: str, user_id: str = Depends(get_current_user)):
    return await service.follow_rider(user_id, rider_id)


@router.delete(
    "/{rider_id}/follow",
    response_model=RiderOut,
    summary="Dejar de seguir a un rider",
    description=(
        "Elimina al rider autenticado de la lista de seguidores del rider especificado. Operación "
        "idempotente: si no lo seguía, retorna 200 sin error."
    ),
)
async def unfollow(rider_id: str, user_id: str = Depends(get_current_user)):
    return await service.unfollow_rider(user_id, rider_id)


@router.get(
    "/{rider_id}/stats",
    response_model=StatsOut,
    summary="Estadísticas del rider",
    description=(
        "Retorna métricas agregadas del rider: número de amarres, kilómetros totales y grupos activos. "
        "En esta versión retorna placeholders; se completará en Sprint 2 con datos reales de MS-Amarres."
    ),
)
async def get_stats(rider_id: str):
    return await service.get_stats(rider_id)
