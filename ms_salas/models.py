from datetime import datetime
from typing import List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


class MiembroDocument(BaseModel):
    rider_id: str
    display_name: str
    role: Literal["admin", "rider", "guest"] = "rider"
    joined_at: datetime = Field(default_factory=datetime.utcnow)


class SalaDocument(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: Optional[str] = Field(default=None, alias="_id")
    name: str
    description: Optional[str] = None
    owner_id: str
    status: Literal["active", "closed"] = "active"
    is_private: bool = False
    miembros: List[MiembroDocument] = Field(default_factory=list)
    qr_token: Optional[str] = None
    invite_link: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    closed_at: Optional[datetime] = None
