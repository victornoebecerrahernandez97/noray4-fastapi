from datetime import datetime
from typing import List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


class SalaCreate(BaseModel):
    name: str = Field(min_length=2, max_length=80)
    description: Optional[str] = Field(default=None, max_length=300)
    is_private: bool = False


class SalaUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=2, max_length=80)
    description: Optional[str] = Field(default=None, max_length=300)
    is_private: Optional[bool] = None


class JoinRequest(BaseModel):
    qr_token: Optional[str] = None


class MiembroOut(BaseModel):
    rider_id: str
    display_name: str
    role: Literal["admin", "rider", "guest"]
    joined_at: datetime


class SalaOut(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str = Field(alias="_id")
    name: str
    description: Optional[str] = None
    owner_id: str
    status: Literal["active", "closed"]
    is_private: bool
    miembros: List[MiembroOut]
    qr_token: Optional[str] = None
    invite_link: Optional[str] = None
    created_at: datetime
    closed_at: Optional[datetime] = None


class QROut(BaseModel):
    qr_token: str
    invite_link: str
