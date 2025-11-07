from __future__ import annotations
from datetime import datetime
from typing import Optional, Literal, List
from pydantic import BaseModel, Field, field_serializer
from .sub_projects import SubProjectOut


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
    
    model_config = {"from_attributes": True}
    
class ProjectDetailOut(ProjectOut):
    subprojects: List[SubProjectOut] = []
   
    model_config = {"from_attributes": True}
