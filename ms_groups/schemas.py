from datetime import datetime
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


class GrupoCreate(BaseModel):
    name: str = Field(min_length=2, max_length=80)
    description: Optional[str] = Field(default=None, max_length=500)
    public: bool = True
    tags: List[str] = Field(default_factory=list, max_length=10)


class GrupoUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=2, max_length=80)
    description: Optional[str] = Field(default=None, max_length=500)
    public: Optional[bool] = None
    tags: Optional[List[str]] = Field(default=None, max_length=10)
    logo_url: Optional[str] = None


class MiembroGrupoOut(BaseModel):
    rider_id: str
    display_name: str
    avatar_url: Optional[str] = None
    role: Literal["admin", "rider"]
    joined_at: datetime


class GrupoOut(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str = Field(alias="_id")
    name: str
    description: Optional[str] = None
    owner_id: str
    logo_url: Optional[str] = None
    miembros: List[Dict[str, Any]] = Field(default_factory=list)
    salas_ids: List[str] = Field(default_factory=list)
    public: bool = True
    tags: List[str] = Field(default_factory=list)
    stats: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: Optional[datetime] = None


class GrupoPublicOut(BaseModel):
    """Versión reducida para búsqueda — sin salas_ids ni lista completa de miembros."""
    model_config = ConfigDict(populate_by_name=True)

    id: str = Field(alias="_id")
    name: str
    description: Optional[str] = None
    owner_id: str
    logo_url: Optional[str] = None
    public: bool
    tags: List[str] = Field(default_factory=list)
    stats: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime


class PaginatedGrupos(BaseModel):
    items: List[GrupoOut]
    total: int
    skip: int
    limit: int
    has_more: bool


class InviteOut(BaseModel):
    invite_link: str
    token: str


class ChangeRoleRequest(BaseModel):
    new_role: Literal["admin", "rider"]
