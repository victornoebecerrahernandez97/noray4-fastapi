from typing import List, Optional

from fastapi import APIRouter, Depends, Form, Query, UploadFile, status

from shared.dependencies import get_current_rider
from ms_amarres.schemas import AmarreCreate, AmarreOut, AmarrePublicOut, AmarreUpdate, CloneOut, PaginatedAmarres
from ms_amarres import service

router = APIRouter(prefix="/amarres", tags=["amarres"])


@router.post(
    "",
    response_model=AmarreOut,
    status_code=status.HTTP_201_CREATED,
    summary="Crear amarre manual",
    description=(
        "Crea un amarre de viaje manualmente sin sala de origen. "
        "El rider autenticado es owner y único participante inicial. "
        "privacy puede ser private, group o public."
    ),
)
async def create_amarre(body: AmarreCreate, rider: dict = Depends(get_current_rider)):
    return await service.create_amarre_manual(rider["_id"], rider["display_name"], body)


@router.get(
    "/me",
    response_model=PaginatedAmarres,
    summary="Mis amarres",
    description="Retorna los amarres del rider autenticado paginados por fecha descendente. Hard cap: 50 por request.",
)
async def get_mis_amarres(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=50),
    rider: dict = Depends(get_current_rider),
):
    return await service.get_mis_amarres(rider["_id"], skip=skip, limit=limit)


@router.get(
    "/feed",
    response_model=PaginatedAmarres,
    summary="Feed de amarres públicos",
    description=(
        "Retorna amarres con privacy=public ordenados por fecha descendente. "
        "Versión reducida sin gpx_data ni chat_log para mayor rendimiento."
    ),
)
async def get_feed(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=50),
    rider: dict = Depends(get_current_rider),
):
    return await service.get_amarres_publicos(skip=skip, limit=limit)


@router.get(
    "/sala/{sala_id}",
    response_model=List[AmarreOut],
    summary="Amarres de una sala",
    description="Retorna todos los amarres asociados a una sala específica. Incluye el amarre auto-generado al cierre.",
)
async def get_by_sala(sala_id: str, rider: dict = Depends(get_current_rider)):
    return await service.get_amarres_by_sala(sala_id)


@router.get(
    "/{amarre_id}",
    response_model=AmarreOut,
    summary="Obtener amarre",
    description=(
        "Retorna un amarre por ID. Verifica acceso según privacy: "
        "private → solo owner, group → solo participantes, public → cualquier rider autenticado."
    ),
)
async def get_amarre(amarre_id: str, rider: dict = Depends(get_current_rider)):
    return await service.get_amarre(amarre_id, rider["_id"])


@router.put(
    "/{amarre_id}",
    response_model=AmarreOut,
    summary="Actualizar amarre",
    description="Edita título, descripción, privacidad, tags o playlist. Solo el owner puede modificar.",
)
async def update_amarre(amarre_id: str, body: AmarreUpdate, rider: dict = Depends(get_current_rider)):
    return await service.update_amarre(amarre_id, rider["_id"], body)


@router.delete(
    "/{amarre_id}",
    summary="Eliminar amarre",
    description="Hard delete del amarre. Solo el owner puede eliminar. Operación irreversible.",
)
async def delete_amarre(amarre_id: str, rider: dict = Depends(get_current_rider)):
    return await service.delete_amarre(amarre_id, rider["_id"])


@router.post(
    "/{amarre_id}/fotos",
    response_model=AmarreOut,
    status_code=status.HTTP_201_CREATED,
    summary="Agregar foto al amarre",
    description=(
        "Sube una imagen a Cloudinary en noray4/amarres/{amarre_id}/. "
        "Genera thumbnail w=600. Máximo 50 fotos por amarre. "
        "Solo participantes pueden subir fotos. Acepta jpeg, png, webp. Máx 10 MB."
    ),
)
async def add_foto(
    amarre_id: str,
    file: UploadFile,
    caption: Optional[str] = Form(default=None),
    rider: dict = Depends(get_current_rider),
):
    return await service.add_foto(amarre_id, rider["_id"], file, caption)


@router.delete(
    "/{amarre_id}/fotos/{public_id:path}",
    response_model=AmarreOut,
    summary="Eliminar foto del amarre",
    description="Elimina una foto por public_id de Cloudinary. Solo quien subió la foto o el owner pueden borrarla.",
)
async def delete_foto(amarre_id: str, public_id: str, rider: dict = Depends(get_current_rider)):
    return await service.delete_foto(amarre_id, rider["_id"], public_id)


@router.post(
    "/{amarre_id}/like",
    summary="Toggle like en amarre",
    description=(
        "Si el rider ya dio like lo quita; si no, lo agrega. Idempotente. "
        "Solo funciona en amarres con privacy=public."
    ),
)
async def like_amarre(amarre_id: str, rider: dict = Depends(get_current_rider)):
    return await service.like_amarre(amarre_id, rider["_id"])


@router.post(
    "/{amarre_id}/clone",
    response_model=CloneOut,
    status_code=status.HTTP_201_CREATED,
    summary="Clonar amarre",
    description=(
        "Crea una copia del amarre con title, description, gpx_data, tags y playlist del original. "
        "El nuevo amarre es privado por default. Incrementa clone_count en el original de forma atómica."
    ),
)
async def clone_amarre(amarre_id: str, rider: dict = Depends(get_current_rider)):
    return await service.clone_amarre(amarre_id, rider["_id"], rider["display_name"])
