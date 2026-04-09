from datetime import datetime
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator


class MensajeCreate(BaseModel):
    sala_id: Optional[str] = None  # informativo; el router usa el path param
    type: Literal["text", "image", "coords", "file", "system"] = "text"
    content: Optional[str] = Field(default=None, max_length=4000)
    coords: Optional[Dict[str, Any]] = None   # {lat, lng, label}
    reply_to: Optional[str] = None
    file_meta: Optional[Dict[str, Any]] = None  # {name, size, mime_type}

    @model_validator(mode="after")
    def validate_type_requirements(self) -> "MensajeCreate":
        if self.type == "text" and not self.content:
            raise ValueError("content es requerido para mensajes de tipo text")
        if self.type == "coords" and not self.coords:
            raise ValueError("coords es requerido para mensajes de tipo coords")
        return self


class MensajeUpdate(BaseModel):
    content: str = Field(min_length=1, max_length=4000)


class MensajeOut(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str = Field(alias="_id")
    sala_id: str
    rider_id: str
    display_name: str
    type: Literal["text", "image", "coords", "file", "system"]
    content: Optional[str] = None
    media_url: Optional[str] = None
    media_thumb_url: Optional[str] = None
    coords: Optional[Dict[str, Any]] = None
    file_meta: Optional[Dict[str, Any]] = None
    reply_to: Optional[str] = None
    edited: bool
    deleted: bool
    delivered_to: List[str]
    created_at: datetime
    updated_at: Optional[datetime] = None


class PaginatedMensajes(BaseModel):
    items: List[MensajeOut]
    total: int
    skip: int
    limit: int
    has_more: bool


class ACKRequest(BaseModel):
    mensaje_id: str


class UploadResponse(BaseModel):
    media_url: str
    thumb_url: str
    public_id: str
