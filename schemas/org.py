from __future__ import annotations
from typing import Optional, List
from pydantic import BaseModel, Field


# -------- Department --------
class DepartmentIn(BaseModel):
    dept_name: str = Field(..., min_length=1, max_length=150)
    description: Optional[str] = Field(None, max_length=500)
    created_by: Optional[int] = None


class DepartmentOut(BaseModel):
    dept_id: int
    dept_name: str
    description: Optional[str]

    class Config:
        from_attributes = True


# -------- Sub-Department --------
class SubDepartmentIn(BaseModel):
    dept_id: int
    sub_dept_name: str = Field(..., min_length=1, max_length=150)
    description: Optional[str] = Field(None, max_length=500)
    created_by: Optional[int] = None


class SubDepartmentOut(BaseModel):
    sub_dept_id: int
    dept_id: int
    sub_dept_name: str
    description: Optional[str]

    class Config:
        from_attributes = True


# -------- Designation --------
class DesignationIn(BaseModel):
    designation_name: str = Field(..., min_length=1, max_length=150)
    dept_id: Optional[int] = None
    sub_dept_id: Optional[int] = None
    description: Optional[str] = Field(None, max_length=500)
    created_by: Optional[int] = None


class DesignationOut(BaseModel):
    designation_id: int
    designation_name: str
    dept_id: Optional[int]
    sub_dept_id: Optional[int]
    description: Optional[str]

    class Config:
        from_attributes = True


# -------- Create-All (atomic) --------
class AddAllIn(BaseModel):
    dept_name: str
    sub_dept_name: str
    designation_name: str
    dept_description: Optional[str] = None
    sub_dept_description: Optional[str] = None
    designation_description: Optional[str] = None
    created_by: Optional[int] = None


class AddAllOut(BaseModel):
    dept: DepartmentOut
    sub_dept: SubDepartmentOut
    designation: DesignationOut

# -------- Dept + SubDept tree with designation counts --------
class SubDeptNode(BaseModel):
    sub_dept_id: int
    sub_dept_name: str
    desig_count: int

    class Config:
        from_attributes = True


class DeptTreeOut(BaseModel):
    dept_id: int
    dept_name: str
    desig_count_direct: int          # designations with this dept_id and sub_dept_id IS NULL
    desig_count_total: int           # direct + all sub-dept designations
    sub_depts: List[SubDeptNode] = []

    class Config:
        from_attributes = True

# -------- Update payloads (partial allowed) --------
class DepartmentUpdate(BaseModel):
    dept_name: Optional[str] = Field(None, min_length=1, max_length=150)
    description: Optional[str] = Field(None, max_length=500)
    updated_by: Optional[int] = None


class SubDepartmentUpdate(BaseModel):
    # You may allow moving a sub-dept across departments by changing dept_id (optional)
    dept_id: Optional[int] = None
    sub_dept_name: Optional[str] = Field(None, min_length=1, max_length=150)
    description: Optional[str] = Field(None, max_length=500)
    updated_by: Optional[int] = None


class DesignationUpdate(BaseModel):
    designation_name: Optional[str] = Field(None, min_length=1, max_length=150)
    dept_id: Optional[int] = None
    sub_dept_id: Optional[int] = None
    description: Optional[str] = Field(None, max_length=500)
    updated_by: Optional[int] = None
