from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


class AmarreDocument(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: Optional[str] = Field(default=None, alias="_id")
    sala_id: Optional[str] = None          # None si es creación manual
    owner_id: str                           # rider_id del creador
    title: str
    description: Optional[str] = None
    riders: List[str] = Field(default_factory=list)           # rider_ids
    riders_display: List[Dict[str, Any]] = Field(default_factory=list)  # [{rider_id, display_name, avatar_url}]
    gpx_data: Optional[Dict[str, Any]] = None                 # GPXExport serializado
    km_total: float = 0.0
    duracion_min: int = 0
    fotos: List[Dict[str, Any]] = Field(default_factory=list) # [{url, thumb_url, public_id, rider_id, caption, taken_at}]
    playlist: List[Dict[str, Any]] = Field(default_factory=list)  # [{title, artist, url}]
    chat_log: Optional[str] = None          # referencia o resumen del chat
    privacy: str = "private"               # "private" | "group" | "public"
    tags: List[str] = Field(default_factory=list)
    cloned_from: Optional[str] = None      # _id del amarre original
    clone_count: int = 0
    likes: List[str] = Field(default_factory=list)            # rider_ids
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = None
