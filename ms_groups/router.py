from typing import List, Optional

from fastapi import APIRouter, Depends, Query, UploadFile, status

from shared.dependencies import get_current_rider
from ms_groups.schemas import (
    ChangeRoleRequest,
    GrupoCreate,
    GrupoOut,
    GrupoPublicOut,
    MiembroGrupoOut,
    PaginatedGrupos,
    GrupoUpdate,
)
from ms_groups import service

router = APIRouter(prefix="/groups", tags=["groups"])


@router.post(
    "",
    response_model=GrupoOut,
    status_code=status.HTTP_201_CREATED,
    summary="Crear grupo",
    description=(
        "Crea un grupo permanente de riders. El creador se agrega automáticamente como admin. "
        "stats inicial: {km_total: 0, amarres_count: 0, riders_count: 1}."
    ),
)
async def create_grupo(body: GrupoCreate, rider: dict = Depends(get_current_rider)):
    return await service.create_grupo(rider["_id"], rider["display_name"], rider.get("avatar_url"), body)


@router.get(
    "/search",
    response_model=PaginatedGrupos,
    summary="Buscar grupos públicos",
    description=(
        "Text search por nombre y tags usando índice MongoDB. "
        "Sin query retorna todos los grupos públicos ordenados por fecha. Hard cap: 50."
    ),
)
async def search_grupos(
    q: str = Query(default=""),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=50),
    rider: dict = Depends(get_current_rider),
):
    return await service.search_grupos(q, skip=skip, limit=limit)


@router.get(
    "/me",
    response_model=PaginatedGrupos,
    summary="Mis grupos",
    description="Retorna los grupos donde el rider autenticado es miembro, paginados por fecha descendente.",
)
async def get_mis_grupos(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=50),
    rider: dict = Depends(get_current_rider),
):
    return await service.get_mis_grupos(rider["_id"], skip=skip, limit=limit)


@router.get(
    "/{grupo_id}",
    response_model=GrupoOut,
    summary="Obtener grupo",
    description="Retorna todos los datos del grupo incluyendo miembros, salas y stats. Lanza 404 si no existe.",
)
async def get_grupo(grupo_id: str, rider: dict = Depends(get_current_rider)):
    return await service.get_grupo(grupo_id)


@router.put(
    "/{grupo_id}",
    response_model=GrupoOut,
    summary="Actualizar grupo",
    description="Edita nombre, descripción, visibilidad o tags. Solo admins del grupo pueden editar.",
)
async def update_grupo(grupo_id: str, body: GrupoUpdate, rider: dict = Depends(get_current_rider)):
    return await service.update_grupo(grupo_id, rider["_id"], body)


@router.delete(
    "/{grupo_id}",
    summary="Eliminar grupo",
    description="Hard delete del grupo. Solo el creador original (owner) puede eliminar. Irreversible.",
)
async def delete_grupo(grupo_id: str, rider: dict = Depends(get_current_rider)):
    return await service.delete_grupo(grupo_id, rider["_id"])


@router.post(
    "/{grupo_id}/logo",
    response_model=GrupoOut,
    summary="Subir logo del grupo",
    description=(
        "Sube el logo a Cloudinary en noray4/grupos/{grupo_id}/. "
        "Genera versión cuadrada 400×400. Solo admins. Acepta jpeg, png, webp. Máx 5 MB."
    ),
)
async def upload_logo(grupo_id: str, file: UploadFile, rider: dict = Depends(get_current_rider)):
    return await service.upload_logo(grupo_id, rider["_id"], file)


@router.post(
    "/{grupo_id}/join",
    response_model=GrupoOut,
    summary="Unirse al grupo",
    description=(
        "Agrega al rider autenticado como miembro con role=rider. Solo grupos públicos. "
        "Idempotente: si ya es miembro retorna el grupo sin error ni duplicado."
    ),
)
async def join_grupo(grupo_id: str, rider: dict = Depends(get_current_rider)):
    return await service.join_grupo(grupo_id, rider["_id"], rider["display_name"], rider.get("avatar_url"))


@router.post(
    "/{grupo_id}/leave",
    summary="Salir del grupo",
    description=(
        "Elimina al rider autenticado del grupo. El owner no puede salir sin transferir "
        "la propiedad primero. Decrementa riders_count en stats."
    ),
)
async def leave_grupo(grupo_id: str, rider: dict = Depends(get_current_rider)):
    return await service.leave_grupo(grupo_id, rider["_id"])


@router.delete(
    "/{grupo_id}/members/{target_rider_id}",
    response_model=GrupoOut,
    summary="Expulsar miembro",
    description=(
        "Admin únicamente. Elimina a target_rider_id del grupo. "
        "No se puede expulsar al owner. Lanza 404 si el rider no es miembro."
    ),
)
async def kick_member(
    grupo_id: str,
    target_rider_id: str,
    rider: dict = Depends(get_current_rider),
):
    return await service.kick_member(grupo_id, rider["_id"], target_rider_id)


@router.put(
    "/{grupo_id}/members/{target_rider_id}/role",
    response_model=GrupoOut,
    summary="Cambiar rol de miembro",
    description=(
        "Owner únicamente. Cambia el rol de target_rider_id a admin o rider. "
        "Útil para promover co-admins o degradar admins."
    ),
)
async def change_role(
    grupo_id: str,
    target_rider_id: str,
    body: ChangeRoleRequest,
    rider: dict = Depends(get_current_rider),
):
    return await service.change_role(grupo_id, rider["_id"], target_rider_id, body.new_role)


@router.get(
    "/{grupo_id}/members",
    response_model=List[MiembroGrupoOut],
    summary="Listar miembros",
    description="Retorna la lista completa de miembros del grupo con su rol y fecha de ingreso.",
)
async def get_miembros(grupo_id: str, rider: dict = Depends(get_current_rider)):
    return await service.get_miembros_grupo(grupo_id)


@router.post(
    "/{grupo_id}/salas/{sala_id}",
    summary="Vincular sala al grupo",
    description=(
        "Agrega sala_id al historial de salas del grupo usando $addToSet (idempotente). "
        "Cualquier miembro puede vincular una sala. Útil para agrupar rutas por comunidad."
    ),
)
async def add_sala(grupo_id: str, sala_id: str, rider: dict = Depends(get_current_rider)):
    return await service.add_sala_to_grupo(grupo_id, sala_id, rider["_id"])


@router.get(
    "/{grupo_id}/salas",
    summary="Historial de salas del grupo",
    description="Retorna datos básicos de las salas vinculadas al grupo. Solo miembros pueden ver el historial.",
)
async def get_salas(grupo_id: str, rider: dict = Depends(get_current_rider)):
    return await service.get_salas_grupo(grupo_id, rider["_id"])


@router.post(
    "/{grupo_id}/stats/recalc",
    summary="Recalcular estadísticas del grupo",
    description=(
        "Admin únicamente. Recalcula km_total, amarres_count y riders_count mediante aggregation "
        "sobre la colección de amarres. Operación costosa — invocar solo bajo demanda."
    ),
)
async def recalc_stats(grupo_id: str, rider: dict = Depends(get_current_rider)):
    return await service.recalc_stats(grupo_id, rider["_id"])
