from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field


class RiderDocument(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: Optional[str] = Field(default=None, alias="_id")
    user_id: str
    display_name: str
    city: Optional[str] = None
    bio: Optional[str] = None
    vehicle_type: Optional[str] = None
    vehicle_model: Optional[str] = None
    vehicle_year: Optional[int] = None
    vehicle_km: Optional[int] = None
    avatar_url: Optional[str] = None
    is_admin: bool = False
    followers: List[str] = Field(default_factory=list)
    following: List[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
