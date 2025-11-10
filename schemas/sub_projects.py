# schemas/sub_projects.py
from __future__ import annotations
from datetime import datetime, timezone
from pydantic import BaseModel, field_serializer

UTC = timezone.utc

class SubProjectBase(BaseModel):
    project_id: int
    assigned_by: int
    assigned_to: int
    description: str | None = None
    project_status: str

class SubProjectCreate(SubProjectBase):
    pass

class SubProjectUpdate(BaseModel):
    description: str | None = None
    project_status: str | None = None
    assigned_to: int | None = None

class SubProjectOut(SubProjectBase):
    subproject_id: int
    created_on: datetime
    last_modified: datetime

    @field_serializer("created_on", "last_modified", when_used="json")
    def _ser_dt(self, dt: datetime, _info):
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=UTC)
        return dt.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%S")

    model_config = {"from_attributes": True}
