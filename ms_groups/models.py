from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


class GrupoDocument(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: Optional[str] = Field(default=None, alias="_id")
    name: str
    description: Optional[str] = None
    owner_id: str                              # rider_id del creador
    logo_url: Optional[str] = None
    miembros: List[Dict[str, Any]] = Field(default_factory=list)
    # [{rider_id, display_name, avatar_url, role: "admin"|"rider", joined_at}]
    salas_ids: List[str] = Field(default_factory=list)   # historial de sala_ids
    public: bool = True
    tags: List[str] = Field(default_factory=list)
    stats: Dict[str, Any] = Field(default_factory=dict)  # {km_total, amarres_count, riders_count}
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = None
