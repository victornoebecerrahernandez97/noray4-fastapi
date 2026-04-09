from datetime import datetime
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


class POIDocument(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: Optional[str] = Field(default=None, alias="_id")
    sala_id: Optional[str] = None         # POI asociado a una sala (None = global)
    rider_id: str                          # creador
    display_name: str                      # nombre del rider creador
    category: Literal[
        "gasolinera", "mecanico", "mirador",
        "comida", "hotel", "peligro", "otro",
    ]
    name: str
    description: Optional[str] = None
    lat: float
    lng: float
    public: bool = False                   # visible en mapa global
    likes: List[str] = Field(default_factory=list)  # rider_ids
    created_at: datetime = Field(default_factory=datetime.utcnow)
    # Campo interno GeoJSON para índice 2dsphere — no se expone en POIOut
    # location: {"type": "Point", "coordinates": [lng, lat]}


class TrackPointDocument(BaseModel):
    """Punto de track efímero — almacenado en memoria durante sala activa."""
    rider_id: str
    sala_id: str
    lat: float
    lng: float
    heading: Optional[float] = None
    speed: Optional[float] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)
