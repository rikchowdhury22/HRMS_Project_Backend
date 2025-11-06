from datetime import datetime, timedelta, timezone
from pydantic import BaseModel, field_serializer
from typing import Optional

# Timezone setup
IST = timezone(timedelta(hours=5, minutes=30))
UTC = timezone.utc


class ProjectMemberCreate(BaseModel):
    user_id: int
    designation_id: Optional[int] = None


class ProjectMemberOut(BaseModel):
    project_id: int
    user_id: int
    designation_id: Optional[int]
    added_on: datetime

    # ✅ Convert UTC → IST and format as "05-Nov-2025 06:35:12 PM"
    @field_serializer("added_on", when_used="json")
    def _ser_added_on(self, dt: datetime, _info):
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=UTC)
        dt_ist = dt.astimezone(IST)
        return dt_ist.strftime("%d-%b-%Y %I:%M:%S %p")

    model_config = {"from_attributes": True}
