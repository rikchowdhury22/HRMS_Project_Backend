from datetime import datetime, timedelta, timezone
from pydantic import BaseModel, field_serializer

# Define IST timezone (UTC + 5:30)
IST = timezone(timedelta(hours=5, minutes=30))

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

    @field_serializer("created_on", "last_modified")
    def format_datetime(self, value: datetime, _info):
        if not value:
            return None
        # ✅ Convert from UTC → IST
        value = value.replace(tzinfo=timezone.utc).astimezone(IST)
        return value.strftime("%d-%b-%Y %I:%M:%S %p")

    class Config:
        orm_mode = True
