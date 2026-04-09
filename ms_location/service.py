import logging
from datetime import datetime
from typing import List, Optional

from bson import ObjectId
from fastapi import HTTPException, status
from pymongo import ASCENDING, DESCENDING

from shared.database import get_pois_collection
from ms_location.schemas import CoordUpdate, GPXExport, POICreate, POIUpdate
from ms_location.track_store import track_store

logger = logging.getLogger("noray4.location")

_POI_PROJECTION = {
    "_id": 1, "sala_id": 1, "rider_id": 1, "display_name": 1,
    "category": 1, "name": 1, "description": 1,
    "lat": 1, "lng": 1, "public": 1, "likes": 1, "created_at": 1,
}


# ---------------------------------------------------------------------------
# Startup — índices
# ---------------------------------------------------------------------------

async def ensure_location_indexes() -> None:
    col = get_pois_collection()
    await col.create_index([("location", "2dsphere")], name="geo_2dsphere", background=True)
    await col.create_index([("sala_id", ASCENDING)], name="poi_sala_id", background=True)
    await col.create_index(
        [("public", ASCENDING), ("category", ASCENDING)],
        name="poi_public_category", background=True,
    )
    await col.create_index([("rider_id", ASCENDING)], name="poi_rider_id", background=True)
    logger.info("Índices de POIs verificados")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _oid(value: str) -> ObjectId:
    try:
        return ObjectId(value)
    except Exception:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="ID inválido")


def _serialize(doc: dict) -> dict:
    doc["_id"] = str(doc["_id"])
    return doc


async def _get_poi(poi_id: str) -> dict:
    col = get_pois_collection()
    doc = await col.find_one({"_id": _oid(poi_id)}, _POI_PROJECTION)
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="POI no encontrado")
    return _serialize(doc)


# ---------------------------------------------------------------------------
# POI — CRUD
# ---------------------------------------------------------------------------

async def create_poi(rider_id: str, display_name: str, data: POICreate) -> dict:
    col = get_pois_collection()
    doc = {
        "sala_id": data.sala_id,
        "rider_id": rider_id,
        "display_name": display_name,
        "category": data.category,
        "name": data.name,
        "description": data.description,
        "lat": data.lat,
        "lng": data.lng,
        "public": data.public,
        "likes": [],
        "created_at": datetime.utcnow(),
        # Campo GeoJSON para índice 2dsphere — no expuesto en POIOut
        "location": {"type": "Point", "coordinates": [data.lng, data.lat]},
    }
    result = await col.insert_one(doc)
    doc["_id"] = str(result.inserted_id)
    return {k: v for k, v in doc.items() if k != "location"}


async def get_pois(
    lat: Optional[float] = None,
    lng: Optional[float] = None,
    radius_m: int = 5000,
    category: Optional[str] = None,
    public_only: bool = True,
    sala_id: Optional[str] = None,
    limit: int = 100,
) -> List[dict]:
    col = get_pois_collection()
    query: dict = {}

    if lat is not None and lng is not None:
        # Requiere índice 2dsphere
        query["location"] = {
            "$near": {
                "$geometry": {"type": "Point", "coordinates": [lng, lat]},
                "$maxDistance": radius_m,
            }
        }

    if public_only:
        query["public"] = True
    if category:
        query["category"] = category
    if sala_id:
        query["sala_id"] = sala_id

    cursor = col.find(query, _POI_PROJECTION).limit(min(limit, 200))
    return [_serialize(doc) async for doc in cursor]


async def get_poi_by_id(poi_id: str) -> dict:
    return await _get_poi(poi_id)


async def update_poi(poi_id: str, rider_id: str, data: POIUpdate) -> dict:
    poi = await _get_poi(poi_id)
    if poi["rider_id"] != rider_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Solo el creador puede editar este POI")

    patch = data.model_dump(exclude_none=True)
    if not patch:
        return poi

    col = get_pois_collection()
    result = await col.find_one_and_update(
        {"_id": _oid(poi_id)},
        {"$set": patch},
        projection=_POI_PROJECTION,
        return_document=True,
    )
    return _serialize(result)


async def delete_poi(poi_id: str, rider_id: str) -> dict:
    poi = await _get_poi(poi_id)
    if poi["rider_id"] != rider_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Solo el creador puede eliminar este POI")

    col = get_pois_collection()
    await col.delete_one({"_id": _oid(poi_id)})
    return {"status": "ok", "detail": "POI eliminado"}


async def toggle_like(poi_id: str, rider_id: str) -> dict:
    """Idempotente: si ya tiene like lo quita, si no lo agrega."""
    await _get_poi(poi_id)  # validates existence
    col = get_pois_collection()

    # Verificar si ya tiene like
    has_like = await col.find_one({"_id": _oid(poi_id), "likes": rider_id})
    op = "$pull" if has_like else "$addToSet"

    result = await col.find_one_and_update(
        {"_id": _oid(poi_id)},
        {op: {"likes": rider_id}},
        projection=_POI_PROJECTION,
        return_document=True,
    )
    return _serialize(result)


# ---------------------------------------------------------------------------
# Track — delegado a TrackStore (in-memory)
# ---------------------------------------------------------------------------

def add_track_point(sala_id: str, point: CoordUpdate) -> None:
    track_store.add_point(sala_id, point.rider_id, point)


def update_position(sala_id: str, point: CoordUpdate) -> dict:
    """Almacena el punto en TrackStore y publica al topic MQTT. Retorna last_positions."""
    track_store.add_point(sala_id, point.rider_id, point)

    try:
        from ms_realtime.mqtt_client import mqtt_gateway
        mqtt_gateway.publish(
            f"noray4/{sala_id}/ubicacion",
            point.model_dump(mode="json"),
        )
    except Exception as exc:
        logger.debug("MQTT publish (ubicacion) ignorado: %s", exc)

    return {"status": "ok", "last_positions": _last_positions(sala_id)}


def _last_positions(sala_id: str) -> dict:
    """Última posición conocida de cada rider activo en la sala."""
    all_tracks = track_store.get_all_tracks(sala_id)
    result = {}
    for rider_id, points in all_tracks.items():
        if points:
            last = points[-1]
            result[rider_id] = last.model_dump(mode="json")
    return result


def get_tracks(sala_id: str) -> dict:
    all_tracks = track_store.get_all_tracks(sala_id)
    return {
        "sala_id": sala_id,
        "riders": [
            {"rider_id": rid, "points": [p.model_dump() for p in pts]}
            for rid, pts in all_tracks.items()
        ],
        "active_riders": len(all_tracks),
    }


def export_gpx(sala_id: str) -> GPXExport:
    return track_store.export_gpx(sala_id)


def clear_tracks(sala_id: str) -> dict:
    track_store.clear_sala(sala_id)
    return {"status": "ok", "detail": f"Tracks de sala {sala_id} limpiados"}
