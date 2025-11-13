# schemas/scrum.py
from __future__ import annotations
from datetime import datetime, date, timezone
from typing import Optional, List, Literal
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
    dependencies: Optional[List[DependencyItem]] = None
    concern: Optional[str] = Field(None, max_length=2000)

    # 🔹 New fields
    scrum_status: Optional[str] = Field(default="Planned")  # default state
    last_action_at: Optional[datetime] = None               # auto-stamped by Mongo


class ScrumUpdate(BaseModel):
    today_task: Optional[str] = Field(None, min_length=1, max_length=2000)
    eta_date: Optional[date] = None
    dependencies: Optional[List[DependencyItem]] = None
    concern: Optional[str] = Field(None, max_length=2000)

    # 🔹 Allow status updates if needed
    scrum_status: Optional[str] = None
    last_action_at: Optional[datetime] = None

class StatusEvent(BaseModel):
    status: str
    note: Optional[str] = None
    actor_id: Optional[int] = None
    at: Optional[datetime] = None
    
class ScrumOut(BaseModel):
    id: str
    subproject_id: int
    user_id: int
    today_task: str
    eta_date: date
    dependencies: Optional[List[DependencyItem]] = None
    concern: Optional[str] = None
    created_at: datetime

    # NEW FIELDS
    scrum_status: Optional[str] = None
    last_action_at: Optional[datetime] = None
    status_events: Optional[List[StatusEvent]] = None

    @field_serializer("created_at", "last_action_at", when_used="json")
    def _ser_dt(self, dt: datetime | None, _info):
        if dt is None:
            return None
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=UTC)
        return dt.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%S")

    model_config = {"from_attributes": True}

class ScrumOutWithHours(ScrumOut):
    work_hours: Optional[float] = None  # populated only when include_hours=true


class ScrumLifecycleAction(BaseModel):
    action: Literal["start", "pause", "end"] = Field(..., description="Lifecycle action")
    note: Optional[str] = Field(None, max_length=2000)
    actor_id: Optional[int] = Field(None, ge=1)
