from datetime import datetime
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


class MensajeDocument(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: Optional[str] = Field(default=None, alias="_id")
    sala_id: str
    rider_id: str
    display_name: str
    type: Literal["text", "image", "coords", "file", "system"] = "text"
    content: Optional[str] = None
    media_url: Optional[str] = None        # Cloudinary secure URL
    media_thumb_url: Optional[str] = None  # Cloudinary eager transform (w=400)
    coords: Optional[Dict[str, Any]] = None   # {lat, lng, label}
    file_meta: Optional[Dict[str, Any]] = None  # {name, size, mime_type}
    reply_to: Optional[str] = None         # _id del mensaje citado
    edited: bool = False
    deleted: bool = False                  # soft delete
    delivered_to: List[str] = Field(default_factory=list)  # rider_ids con ACK
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = None
