from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field


class MotoUpdate(BaseModel):
    modelo: str = Field(min_length=1, max_length=80)
    año: int = Field(ge=1900, le=2100)
    km: int = Field(ge=0)


class RiderCreate(BaseModel):
    display_name: str = Field(min_length=2, max_length=60)
    city: Optional[str] = Field(default=None, max_length=80)
    bio: Optional[str] = Field(default=None, max_length=160)
    vehicle_type: Optional[str] = Field(default=None, max_length=40)
    avatar_url: Optional[str] = Field(default=None)


class RiderUpdate(BaseModel):
    display_name: Optional[str] = Field(default=None, min_length=2, max_length=60)
    city: Optional[str] = Field(default=None, max_length=80)
    bio: Optional[str] = Field(default=None, max_length=160)
    avatar_url: Optional[str] = Field(default=None)


class RiderOut(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str = Field(alias="_id")
    user_id: str
    display_name: str
    city: Optional[str] = None
    bio: Optional[str] = None
    vehicle_type: Optional[str] = None
    vehicle_model: Optional[str] = None
    vehicle_year: Optional[int] = None
    vehicle_km: Optional[int] = None
    avatar_url: Optional[str] = None
    followers: List[str] = Field(default_factory=list)
    following: List[str] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class StatsOut(BaseModel):
    amarres: int
    km_totales: int
    grupos: int
