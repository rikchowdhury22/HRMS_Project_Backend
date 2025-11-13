# schemas/project_members.py
from __future__ import annotations
from datetime import datetime, timezone
from pydantic import BaseModel, field_serializer
from typing import Optional

UTC = timezone.utc

class ProjectMemberCreate(BaseModel):
    user_id: int
    designation_id: Optional[int] = None

class ProjectMemberOut(BaseModel):
    project_id: int
    user_id: int
    designation_id: Optional[int]
    added_on: datetime

    @field_serializer("added_on", when_used="json")
    def _ser_added_on(self, dt: datetime, _info):
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=UTC)
        return dt.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%S")

    model_config = {"from_attributes": True}
