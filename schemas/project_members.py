from datetime import datetime
from pydantic import BaseModel, field_serializer
from typing import Optional

class ProjectMemberCreate(BaseModel):
    user_id: int
    designation_id: Optional[int] = None


class ProjectMemberOut(BaseModel):
    project_id: int
    user_id: int
    designation_id: Optional[int]
    added_on: datetime

    model_config = {"from_attributes": True}
