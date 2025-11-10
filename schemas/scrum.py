# schemas/scrum.py
from __future__ import annotations
from datetime import datetime, date, timezone
from typing import Optional, List
from pydantic import BaseModel, Field, field_serializer

UTC = timezone.utc


class DependencyItem(BaseModel):
    user_id: int = Field(..., ge=1)
    description: str = Field(..., min_length=1, max_length=2000)


class ScrumCreate(BaseModel):
    user_id: int = Field(..., ge=1)
    subproject_id: int = Field(..., ge=1)
    today_task: str = Field(..., min_length=1, max_length=2000)
    eta_date: date
    dependencies: Optional[List[DependencyItem]] = None   # ✅ list of objects
    concern: Optional[str] = Field(None, max_length=2000)


class ScrumUpdate(BaseModel):
    today_task: Optional[str] = Field(None, min_length=1, max_length=2000)
    eta_date: Optional[date] = None
    dependencies: Optional[List[DependencyItem]] = None
    concern: Optional[str] = Field(None, max_length=2000)


class ScrumOut(BaseModel):
    id: str
    subproject_id: int
    user_id: int
    today_task: str
    eta_date: date
    dependencies: Optional[List[DependencyItem]] = None
    concern: Optional[str] = None
    created_at: datetime

    @field_serializer("created_at", when_used="json")
    def _ser_created_at(self, dt: datetime, _info):
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=UTC)
        return dt.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%S")

    model_config = {"from_attributes": True}
