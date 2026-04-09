from typing import List, Optional

from fastapi import APIRouter, Depends, Query, status

from shared.dependencies import get_current_rider
from ms_location.schemas import CoordUpdate, GPXExport, POICreate, POIOut, POIUpdate
from ms_location import service

router = APIRouter(prefix="/location", tags=["location"])


# ---------------------------------------------------------------------------
# POIs
# ---------------------------------------------------------------------------

@router.post(
    "/pois",
    response_model=POIOut,
    status_code=status.HTTP_201_CREATED,
    summary="Crear punto de interés",
    description=(
        "Persiste un POI en MongoDB con índice geoespacial 2dsphere. "
        "Puede asociarse a una sala (sala_id) o ser global (public=True)."
    ),
)
async def create_poi(body: POICreate, rider: dict = Depends(get_current_rider)):
    return await service.create_poi(rider["_id"], rider["display_name"], body)


@router.get(
    "/pois",
    response_model=List[POIOut],
    summary="Listar POIs",
    description=(
        "Retorna POIs filtrados por categoría, sala o radio geográfico. "
        "Si se pasan lat/lng usa $near (requiere índice 2dsphere). Máx 200 resultados."
    ),
)
async def list_pois(
    lat: Optional[float] = Query(default=None, ge=-90, le=90),
    lng: Optional[float] = Query(default=None, ge=-180, le=180),
    radius_m: int = Query(default=5000, ge=100, le=50000),
    category: Optional[str] = Query(default=None),
    sala_id: Optional[str] = Query(default=None),
    public_only: bool = Query(default=True),
    limit: int = Query(default=50, ge=1, le=200),
    rider: dict = Depends(get_current_rider),
):
    return await service.get_pois(
        lat=lat, lng=lng, radius_m=radius_m,
        category=category, public_only=public_only,
        sala_id=sala_id, limit=limit,
    )


@router.get(
    "/pois/{poi_id}",
    response_model=POIOut,
    summary="Obtener POI por ID",
    description="Retorna un POI específico. Lanza 404 si no existe.",
)
async def get_poi(poi_id: str, rider: dict = Depends(get_current_rider)):
    return await service.get_poi_by_id(poi_id)


@router.put(
    "/pois/{poi_id}",
    response_model=POIOut,
    summary="Actualizar POI",
    description="Actualiza nombre, descripción, categoría o visibilidad. Solo el creador puede editar.",
)
async def update_poi(poi_id: str, body: POIUpdate, rider: dict = Depends(get_current_rider)):
    return await service.update_poi(poi_id, rider["_id"], body)


@router.delete(
    "/pois/{poi_id}",
    summary="Eliminar POI",
    description="Elimina físicamente el POI. Solo el creador puede borrar. Lanza 403 en caso contrario.",
)
async def delete_poi(poi_id: str, rider: dict = Depends(get_current_rider)):
    return await service.delete_poi(poi_id, rider["_id"])


@router.post(
    "/pois/{poi_id}/like",
    response_model=POIOut,
    summary="Toggle like en POI",
    description=(
        "Si el rider ya dio like lo quita; si no lo tenía lo agrega. "
        "Idempotente y seguro para doble tap."
    ),
)
async def toggle_like(poi_id: str, rider: dict = Depends(get_current_rider)):
    return await service.toggle_like(poi_id, rider["_id"])


# ---------------------------------------------------------------------------
# Tracks (in-memory)
# ---------------------------------------------------------------------------

@router.post(
    "/salas/{sala_id}/update",
    summary="Actualizar posición del rider",
    description=(
        "Registra la posición GPS actual del rider en la sala. Almacena el punto en el TrackStore "
        "en memoria y publica las coordenadas al topic MQTT de ubicación. Retorna la última posición "
        "conocida de todos los riders activos en la sala."
    ),
)
async def update_position(
    sala_id: str,
    body: CoordUpdate,
    rider: dict = Depends(get_current_rider),
):
    body = body.model_copy(update={"rider_id": rider["_id"]})
    return service.update_position(sala_id, body)


@router.get(
    "/salas/{sala_id}/tracks",
    summary="Obtener tracks activos de la sala",
    description=(
        "Retorna todos los puntos de track en memoria para cada rider activo. "
        "Datos efímeros — se pierden al reiniciar el servidor o al llamar /clear."
    ),
)
async def get_tracks(sala_id: str, rider: dict = Depends(get_current_rider)):
    return service.get_tracks(sala_id)


@router.get(
    "/salas/{sala_id}/export",
    response_model=GPXExport,
    summary="Exportar tracks como GPXExport",
    description=(
        "Genera la estructura GPXExport con todos los tracks de la sala. "
        "Lista para persistir en MS-Amarres al cierre. En Sprint 2 se añade serialización XML GPX."
    ),
)
async def export_gpx(sala_id: str, rider: dict = Depends(get_current_rider)):
    return service.export_gpx(sala_id)


@router.post(
    "/salas/{sala_id}/clear",
    summary="Limpiar tracks de la sala",
    description=(
        "Elimina todos los tracks en memoria de la sala. "
        "Llamado automáticamente por MS-Salas al cerrar una sala (Sprint 2)."
    ),
)
async def clear_tracks(sala_id: str, rider: dict = Depends(get_current_rider)):
    return service.clear_tracks(sala_id)
