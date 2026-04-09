from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class CanalVozDocument(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: Optional[str] = Field(default=None, alias="_id")
    sala_id: str
    name: str  # "general" | "lideres" | "emergencia" | custom
    created_by: str  # rider_id
    activo: bool = True
    created_at: datetime = Field(default_factory=datetime.utcnow)
