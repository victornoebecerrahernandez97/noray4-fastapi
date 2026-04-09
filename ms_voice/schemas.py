from datetime import datetime
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


class CanalCreate(BaseModel):
    name: str = Field(min_length=2, max_length=60)
    sala_id: str


class CanalOut(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str = Field(alias="_id")
    sala_id: str
    name: str
    activo: bool
    created_by: str
    created_at: datetime


class PTTRequest(BaseModel):
    canal_id: str
    action: Literal["start", "stop"]


class PTTState(BaseModel):
    canal_id: str
    sala_id: str
    speaker_id: Optional[str] = None
    speaker_name: Optional[str] = None
    is_speaking: bool = False
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class WebRTCSignal(BaseModel):
    type: Literal["offer", "answer", "ice-candidate"]
    target_rider_id: str
    payload: Dict[str, Any]
    canal_id: str


class VozStatusOut(BaseModel):
    canal_id: str
    canal_name: str
    is_speaking: bool
    speaker_id: Optional[str] = None
    speaker_name: Optional[str] = None
    participants: List[str] = []  # rider_ids activos en el canal esta sesión
