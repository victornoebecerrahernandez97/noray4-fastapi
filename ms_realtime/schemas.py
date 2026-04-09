from datetime import datetime
from typing import Any, Dict, Literal, Optional

from pydantic import BaseModel, Field


class UbicacionPayload(BaseModel):
    rider_id: str
    lat: float = Field(ge=-90, le=90)
    lng: float = Field(ge=-180, le=180)
    heading: Optional[float] = Field(default=None, ge=0, le=360)
    speed: Optional[float] = Field(default=None, ge=0)
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class ChatPayload(BaseModel):
    rider_id: str
    display_name: str
    message: str = Field(min_length=1, max_length=1000)
    type: Literal["text", "image", "coords"] = "text"
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class PresenciaPayload(BaseModel):
    rider_id: str
    display_name: str
    status: Literal["online", "offline"]
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class EventoPayload(BaseModel):
    type: str = Field(min_length=1, max_length=60)
    data: Dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=datetime.utcnow)
