from __future__ import annotations
from datetime import datetime, timedelta, timezone
from typing import Optional, Literal
from pydantic import BaseModel, Field, field_serializer

# ✅ Works on all OSes — no zoneinfo dependency
IST = timezone(timedelta(hours=5, minutes=30))
UTC = timezone.utc


class ProjectCreate(BaseModel):
    project_name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    project_status: Literal["Active", "Completed", "On Hold"] = "Active"
    created_by: int


class ProjectUpdate(BaseModel):
    project_name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    project_status: Optional[Literal["Active", "Completed", "On Hold"]] = None


class ProjectOut(BaseModel):
    project_id: int
    project_name: str
    description: Optional[str] = None
    project_status: str
    created_by: int
    created_on: datetime
    last_modified: datetime

    # 🔥 Converts both fields to IST 12-hour format on JSON serialization
    @field_serializer("created_on", "last_modified", when_used="json")
    def _format_datetime(self, dt: datetime, _info):
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=UTC)
        dt_ist = dt.astimezone(IST)
        return dt_ist.strftime("%d-%b-%Y %I:%M:%S %p")  # e.g. 05-Nov-2025 02:45:08 PM

    model_config = {"from_attributes": True}
