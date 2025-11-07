from datetime import datetime
from pydantic import BaseModel, ConfigDict
from typing import Optional

class SubProjectBase(BaseModel):
    project_id: int
    assigned_by: int
    assigned_to: int
    description: Optional[str] = None
    project_status: str
    subproject_name: Optional[str] = None
    subproject_deadline: Optional[datetime] = None  # or date

class SubProjectCreate(SubProjectBase):
    pass

class SubProjectUpdate(BaseModel):
    description: Optional[str] = None
    project_status: Optional[str] = None
    assigned_to: Optional[int] = None
    subproject_name: Optional[str] = None
    subproject_deadline: Optional[datetime] = None  # or date

class SubProjectOut(SubProjectBase):
    model_config = ConfigDict(from_attributes=True)  # ← Important for ORM objects

    subproject_id: int
    created_on: datetime
    last_modified: datetime
