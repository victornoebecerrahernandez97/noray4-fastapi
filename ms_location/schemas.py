from datetime import datetime
from typing import Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Track (ephemeral, in-memory)
# ---------------------------------------------------------------------------

class CoordUpdate(BaseModel):
    rider_id: Optional[str] = None  # sobreescrito por el JWT en el endpoint; nunca del body
    lat: float = Field(ge=-90, le=90)
    lng: float = Field(ge=-180, le=180)
    heading: Optional[float] = Field(default=None, ge=0, le=360)
    speed: Optional[float] = Field(default=None, ge=0)
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class TrackOut(BaseModel):
    rider_id: str
    points: List[CoordUpdate]


class GPXExport(BaseModel):
    sala_id: str
    riders: List[TrackOut]
    exported_at: datetime = Field(default_factory=datetime.utcnow)


# ---------------------------------------------------------------------------
# POI (persisted in MongoDB)
# ---------------------------------------------------------------------------

class POICreate(BaseModel):
    category: Literal[
        "gasolinera", "mecanico", "mirador",
        "comida", "hotel", "peligro", "otro",
    ]
    name: str = Field(min_length=2, max_length=100)
    description: Optional[str] = Field(default=None, max_length=500)
    lat: float = Field(ge=-90, le=90)
    lng: float = Field(ge=-180, le=180)
    public: bool = False
    sala_id: Optional[str] = None


class POIUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=2, max_length=100)
    description: Optional[str] = Field(default=None, max_length=500)
    category: Optional[Literal[
        "gasolinera", "mecanico", "mirador",
        "comida", "hotel", "peligro", "otro",
    ]] = None
    public: Optional[bool] = None


class POIOut(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str = Field(alias="_id")
    sala_id: Optional[str] = None
    rider_id: str
    display_name: str
    category: str
    name: str
    description: Optional[str] = None
    lat: float
    lng: float
    public: bool
    likes: List[str]
    created_at: datetime
