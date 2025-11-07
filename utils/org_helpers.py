from __future__ import annotations
from typing import Optional
from fastapi import HTTPException
from sqlalchemy import select, func
from sqlalchemy.orm import Session
from datetime import datetime
from models import Department, SubDepartment, Designation


def _norm(s: str) -> str:
    """Normalize names for idempotency (trim & collapse spaces; case-insensitive checks)."""
    return " ".join(s.strip().split())


def get_or_create_department(
        db: Session, name: str, description: Optional[str], created_by: Optional[int]
) -> Department:
    norm = _norm(name)
    existing = db.scalar(select(Department).where(func.lower(Department.dept_name) == norm.lower()))
    if existing:
        return existing
    d = Department(dept_name=norm, description=description, created_by=created_by)
    db.add(d)
    db.flush()
    return d


def get_or_create_subdept(
        db: Session, dept_id: int, name: str, description: Optional[str], created_by: Optional[int]
) -> SubDepartment:
    norm = _norm(name)
    dept = db.get(Department, dept_id)
    if not dept:
        raise HTTPException(status_code=404, detail="Department not found")

    existing = db.scalar(
        select(SubDepartment).where(
            SubDepartment.dept_id == dept_id,
            func.lower(SubDepartment.sub_dept_name) == norm.lower(),
        )
    )
    if existing:
        return existing

    sd = SubDepartment(dept_id=dept_id, sub_dept_name=norm, description=description, created_by=created_by)
    db.add(sd)
    db.flush()
    return sd


def get_or_create_designation(
        db: Session,
        name: str,
        dept_id: Optional[int],
        sub_dept_id: Optional[int],
        description: Optional[str],
        created_by: Optional[int],
) -> Designation:
    norm = _norm(name)

    if dept_id is not None and not db.get(Department, dept_id):
        raise HTTPException(status_code=404, detail="Department not found for designation")
    if sub_dept_id is not None and not db.get(SubDepartment, sub_dept_id):
        raise HTTPException(status_code=404, detail="Sub-Department not found for designation")

    # Uniqueness scoped by (name, dept_id, sub_dept_id)
    existing = db.scalar(
        select(Designation).where(
            func.lower(Designation.designation_name) == norm.lower(),
            (Designation.dept_id == dept_id) if dept_id is not None else Designation.dept_id.is_(None),
            (Designation.sub_dept_id == sub_dept_id) if sub_dept_id is not None else Designation.sub_dept_id.is_(None),
        )
    )
    if existing:
        return existing

    desig = Designation(
        designation_name=norm,
        dept_id=dept_id,
        sub_dept_id=sub_dept_id,
        description=description,
        created_by=created_by,
    )
    db.add(desig)
    db.flush()
    return desig

def _now_utc() -> datetime:
    return datetime.utcnow()


def update_department(
    db: Session, dept_id: int, *, dept_name: Optional[str], description: Optional[str], updated_by: Optional[int]
) -> Department:
    d = db.get(Department, dept_id)
    if not d:
        raise HTTPException(status_code=404, detail="Department not found")

    if dept_name is not None:
        norm = _norm(dept_name)
        # unique name check (ignore self)
        conflict = db.scalar(
            select(Department).where(func.lower(Department.dept_name) == norm.lower(), Department.dept_id != dept_id)
        )
        if conflict:
            raise HTTPException(status_code=409, detail="Another department with this name already exists")
        d.dept_name = norm

    if description is not None:
        d.description = description

    d.updated_by = updated_by
    d.updated_at = _now_utc()
    db.flush()
    return d


def update_subdept(
    db: Session,
    sub_dept_id: int,
    *,
    dept_id: Optional[int],
    sub_dept_name: Optional[str],
    description: Optional[str],
    updated_by: Optional[int],
) -> SubDepartment:
    sd = db.get(SubDepartment, sub_dept_id)
    if not sd:
        raise HTTPException(status_code=404, detail="Sub-Department not found")

    # If target dept_id changes, verify the new parent exists
    target_dept_id = sd.dept_id if dept_id is None else dept_id
    if target_dept_id != sd.dept_id and not db.get(Department, target_dept_id):
        raise HTTPException(status_code=404, detail="Target Department not found")

    # Check uniqueness (sub_dept_name per dept)
    target_name = sd.sub_dept_name if sub_dept_name is None else _norm(sub_dept_name)
    conflict = db.scalar(
        select(SubDepartment).where(
            SubDepartment.dept_id == target_dept_id,
            func.lower(SubDepartment.sub_dept_name) == target_name.lower(),
            SubDepartment.sub_dept_id != sub_dept_id,
        )
    )
    if conflict:
        raise HTTPException(status_code=409, detail="Sub-Department with this name already exists in the target department")

    # Apply updates
    sd.dept_id = target_dept_id
    if sub_dept_name is not None:
        sd.sub_dept_name = target_name
    if description is not None:
        sd.description = description

    sd.updated_by = updated_by
    sd.updated_at = _now_utc()
    db.flush()
    return sd


def update_designation(
    db: Session,
    designation_id: int,
    *,
    designation_name: Optional[str],
    dept_id: Optional[int],
    sub_dept_id: Optional[int],
    description: Optional[str],
    updated_by: Optional[int],
) -> Designation:
    des = db.get(Designation, designation_id)
    if not des:
        raise HTTPException(status_code=404, detail="Designation not found")

    # Determine new scope
    new_name = des.designation_name if designation_name is None else _norm(designation_name)
    new_dept_id = des.dept_id if dept_id is None else dept_id
    new_sub_id = des.sub_dept_id if sub_dept_id is None else sub_dept_id

    # Validate scope
    if new_dept_id is not None and not db.get(Department, new_dept_id):
        raise HTTPException(status_code=404, detail="Department not found for designation")
    if new_sub_id is not None and not db.get(SubDepartment, new_sub_id):
        raise HTTPException(status_code=404, detail="Sub-Department not found for designation")

    # Enforce unique (name, dept_id, sub_dept_id)
    conflict = db.scalar(
        select(Designation).where(
            func.lower(Designation.designation_name) == new_name.lower(),
            (Designation.dept_id == new_dept_id) if new_dept_id is not None else Designation.dept_id.is_(None),
            (Designation.sub_dept_id == new_sub_id) if new_sub_id is not None else Designation.sub_dept_id.is_(None),
            Designation.designation_id != designation_id,
        )
    )
    if conflict:
        raise HTTPException(status_code=409, detail="Designation with this name already exists in the given scope")

    # Apply updates
    des.designation_name = new_name
    des.dept_id = new_dept_id
    des.sub_dept_id = new_sub_id
    if description is not None:
        des.description = description

    des.updated_by = updated_by
    des.updated_at = _now_utc()
    db.flush()
    return des


def delete_department_safe(db: Session, dept_id: int) -> None:
    d = db.get(Department, dept_id)
    if not d:
        raise HTTPException(status_code=404, detail="Department not found")

    # Block delete if children exist
    has_subs = db.scalar(select(func.count()).select_from(SubDepartment).where(SubDepartment.dept_id == dept_id)) or 0
    has_direct_desigs = db.scalar(
        select(func.count()).select_from(Designation).where(
            Designation.dept_id == dept_id, Designation.sub_dept_id.is_(None)
        )
    ) or 0
    has_sub_desigs = db.scalar(
        select(func.count()).select_from(Designation).where(
            Designation.dept_id == dept_id, Designation.sub_dept_id.is_not(None)
        )
    ) or 0
    if has_subs or has_direct_desigs or has_sub_desigs:
        raise HTTPException(
            status_code=409,
            detail="Cannot delete department with existing sub-departments or designations",
        )

    db.delete(d)
    db.flush()


def delete_subdept_safe(db: Session, sub_dept_id: int) -> None:
    sd = db.get(SubDepartment, sub_dept_id)
    if not sd:
        raise HTTPException(status_code=404, detail="Sub-Department not found")

    # Block delete if designations attached
    has_desigs = db.scalar(
        select(func.count()).select_from(Designation).where(Designation.sub_dept_id == sub_dept_id)
    ) or 0
    if has_desigs:
        raise HTTPException(status_code=409, detail="Cannot delete sub-department with existing designations")

    db.delete(sd)
    db.flush()


def delete_designation(db: Session, designation_id: int) -> None:
    des = db.get(Designation, designation_id)
    if not des:
        raise HTTPException(status_code=404, detail="Designation not found")
    db.delete(des)
    db.flush()
