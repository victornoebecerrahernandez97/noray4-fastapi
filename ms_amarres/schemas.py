from datetime import datetime
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


class PlaylistItem(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    artist: Optional[str] = Field(default=None, max_length=200)
    url: Optional[str] = None


class AmarreCreate(BaseModel):
    title: str = Field(min_length=2, max_length=120)
    description: Optional[str] = Field(default=None, max_length=1000)
    privacy: Literal["private", "group", "public"] = "private"
    tags: List[str] = Field(default_factory=list, max_length=10)


class AmarreUpdate(BaseModel):
    title: Optional[str] = Field(default=None, min_length=2, max_length=120)
    description: Optional[str] = Field(default=None, max_length=1000)
    privacy: Optional[Literal["private", "group", "public"]] = None
    tags: Optional[List[str]] = Field(default=None, max_length=10)
    playlist: Optional[List[PlaylistItem]] = None


class FotoAdd(BaseModel):
    caption: Optional[str] = Field(default=None, max_length=300)


class RiderDisplay(BaseModel):
    rider_id: str
    display_name: str
    avatar_url: Optional[str] = None


class AmarreOut(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str = Field(alias="_id")
    sala_id: Optional[str] = None
    owner_id: str
    title: str
    description: Optional[str] = None
    riders: List[str] = Field(default_factory=list)
    riders_display: List[Dict[str, Any]] = Field(default_factory=list)
    gpx_data: Optional[Dict[str, Any]] = None
    km_total: float = 0.0
    duracion_min: int = 0
    fotos: List[Dict[str, Any]] = Field(default_factory=list)
    playlist: List[Dict[str, Any]] = Field(default_factory=list)
    chat_log: Optional[str] = None
    privacy: str = "private"
    tags: List[str] = Field(default_factory=list)
    cloned_from: Optional[str] = None
    clone_count: int = 0
    likes: List[str] = Field(default_factory=list)
    created_at: datetime
    updated_at: Optional[datetime] = None


class AmarrePublicOut(BaseModel):
    """Versión reducida para feed público — sin chat_log ni gpx_data."""
    model_config = ConfigDict(populate_by_name=True)

    id: str = Field(alias="_id")
    owner_id: str
    title: str
    description: Optional[str] = None
    riders_display: List[Dict[str, Any]] = Field(default_factory=list)
    km_total: float = 0.0
    duracion_min: int = 0
    fotos: List[Dict[str, Any]] = Field(default_factory=list)
    privacy: str = "private"
    tags: List[str] = Field(default_factory=list)
    clone_count: int = 0
    likes: List[str] = Field(default_factory=list)
    created_at: datetime


class PaginatedAmarres(BaseModel):
    items: List[AmarreOut]
    total: int
    skip: int
    limit: int
    has_more: bool


class CloneOut(BaseModel):
    original_id: str
    amarre: AmarreOut
