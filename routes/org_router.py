# routes/org_router.py
from __future__ import annotations

from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, status, Response
from sqlalchemy.orm import Session
from sqlalchemy import select, func, tuple_

from db import get_db
from models import Department, SubDepartment, Designation
from schemas.org import (
    DepartmentIn, DepartmentOut,
    SubDepartmentIn, SubDepartmentOut,
    DesignationIn, DesignationOut,
    AddAllIn, AddAllOut, DeptTreeOut, SubDeptNode, DepartmentUpdate, SubDepartmentUpdate, DesignationUpdate,
)
from utils.org_helpers import (
    get_or_create_department,
    get_or_create_subdept,
    get_or_create_designation,
    update_department, update_subdept, update_designation,
    delete_department_safe, delete_subdept_safe, delete_designation,
)

router = APIRouter(prefix="/org", tags=["Organization"])


# -----------------------------
# CREATE (existing)
# -----------------------------
@router.post("/departments", response_model=DepartmentOut)
def create_department(payload: DepartmentIn, db: Session = Depends(get_db)):
    d = get_or_create_department(db, payload.dept_name, payload.description, payload.created_by)
    db.commit()
    return d


@router.post("/sub-departments", response_model=SubDepartmentOut)
def create_sub_department(payload: SubDepartmentIn, db: Session = Depends(get_db)):
    sd = get_or_create_subdept(db, payload.dept_id, payload.sub_dept_name, payload.description, payload.created_by)
    db.commit()
    return sd


@router.post("/designations", response_model=DesignationOut)
def create_designation(payload: DesignationIn, db: Session = Depends(get_db)):
    desig = get_or_create_designation(
        db,
        payload.designation_name,
        payload.dept_id,
        payload.sub_dept_id,
        payload.description,
        payload.created_by,
    )
    db.commit()
    return desig


@router.post("/add-all", response_model=AddAllOut)
def create_all(payload: AddAllIn, db: Session = Depends(get_db)):
    with db.begin():
        dept = get_or_create_department(db, payload.dept_name, payload.dept_description, payload.created_by)
        sub_dept = get_or_create_subdept(
            db, dept.dept_id, payload.sub_dept_name, payload.sub_dept_description, payload.created_by
        )
        designation = get_or_create_designation(
            db, payload.designation_name, dept.dept_id, sub_dept.sub_dept_id, payload.designation_description,
            payload.created_by
        )
    return AddAllOut(dept=dept, sub_dept=sub_dept, designation=designation)


# -----------------------------
# GET (added)
# -----------------------------

# Lists
@router.get("/departments", response_model=List[DepartmentOut])
def list_departments(db: Session = Depends(get_db)):
    rows = db.scalars(select(Department).order_by(Department.dept_name)).all()
    return rows


@router.get("/sub-departments", response_model=List[SubDepartmentOut])
def list_sub_departments(dept_id: Optional[int] = None, db: Session = Depends(get_db)):
    stmt = select(SubDepartment)
    if dept_id is not None:
        stmt = stmt.where(SubDepartment.dept_id == dept_id)
    rows = db.scalars(stmt.order_by(SubDepartment.sub_dept_name)).all()
    return rows


@router.get("/designations", response_model=List[DesignationOut])
def list_designations(
        dept_id: Optional[int] = None,
        sub_dept_id: Optional[int] = None,
        db: Session = Depends(get_db),
):
    stmt = select(Designation)
    if dept_id is not None:
        stmt = stmt.where(Designation.dept_id == dept_id)
    if sub_dept_id is not None:
        stmt = stmt.where(Designation.sub_dept_id == sub_dept_id)
    rows = db.scalars(stmt.order_by(Designation.designation_name)).all()
    return rows


# By ID
@router.get("/departments/{dept_id}", response_model=DepartmentOut)
def get_department(dept_id: int, db: Session = Depends(get_db)):
    row = db.get(Department, dept_id)
    if not row:
        raise HTTPException(status_code=404, detail="Department not found")
    return row


@router.get("/sub-departments/{sub_dept_id}", response_model=SubDepartmentOut)
def get_sub_department(sub_dept_id: int, db: Session = Depends(get_db)):
    row = db.get(SubDepartment, sub_dept_id)
    if not row:
        raise HTTPException(status_code=404, detail="Sub-Department not found")
    return row


@router.get("/designations/{designation_id}", response_model=DesignationOut)
def get_designation(designation_id: int, db: Session = Depends(get_db)):
    row = db.get(Designation, designation_id)
    if not row:
        raise HTTPException(status_code=404, detail="Designation not found")
    return row


# -----------------------------
# ORG STRUCTURE (dept + sub-dept + designation counts)
# -----------------------------
@router.get("/structure", response_model=List[DeptTreeOut])
@router.get("/structure/{dept_id}", response_model=List[DeptTreeOut])
def org_structure(dept_id: Optional[int] = None, db: Session = Depends(get_db)):
    """
    Returns departments with their sub-departments and designation counts.
    - desig_count_direct: designations attached to the department (sub_dept_id is NULL)
    - desig_count_total: direct + all sub-dept designations
    """
    # 1) Pull all designation counts grouped by (dept_id, sub_dept_id)
    desig_counts_rows = db.execute(
        select(
            Designation.dept_id,
            Designation.sub_dept_id,
            func.count(Designation.designation_id).label("n"),
        )
        .group_by(Designation.dept_id, Designation.sub_dept_id)
    ).all()

    # Map: (dept_id, sub_dept_id) -> count
    desig_counts = {(row[0], row[1]): int(row[2]) for row in desig_counts_rows}

    # 2) Fetch departments (optionally filtered)
    dept_stmt = select(Department)
    if dept_id is not None:
        dept_stmt = dept_stmt.where(Department.dept_id == dept_id)
    departments = db.scalars(dept_stmt.order_by(Department.dept_name)).all()

    if dept_id is not None and not departments:
        raise HTTPException(status_code=404, detail="Department not found")

    # 3) Fetch all sub-departments for those departments
    dept_ids = [d.dept_id for d in departments]
    sub_stmt = select(SubDepartment).where(SubDepartment.dept_id.in_(dept_ids)) if dept_ids else select(
        SubDepartment).where(False)
    sub_depts = db.scalars(sub_stmt).all()

    # Organize sub-depts by dept_id
    subs_by_dept: dict[int, list[SubDepartment]] = {}
    for sd in sub_depts:
        subs_by_dept.setdefault(sd.dept_id, []).append(sd)

    # 4) Build response
    result: List[DeptTreeOut] = []
    for d in departments:
        # Count direct designations (sub_dept_id is NULL)
        direct = desig_counts.get((d.dept_id, None), 0)

        # Build sub-nodes and accumulate total
        sub_nodes: List[SubDeptNode] = []
        subs = subs_by_dept.get(d.dept_id, [])
        sub_total = 0
        for sd in sorted(subs, key=lambda x: x.sub_dept_name.lower()):
            n = desig_counts.get((d.dept_id, sd.sub_dept_id), 0)
            sub_total += n
            sub_nodes.append(SubDeptNode(
                sub_dept_id=sd.sub_dept_id,
                sub_dept_name=sd.sub_dept_name,
                desig_count=n,
            ))

        result.append(DeptTreeOut(
            dept_id=d.dept_id,
            dept_name=d.dept_name,
            desig_count_direct=direct,
            desig_count_total=direct + sub_total,
            sub_depts=sub_nodes,
        ))

    return result


# -----------------------------
# UPDATE (partial PUT)
# -----------------------------
@router.put("/departments/{dept_id}", response_model=DepartmentOut)
def update_department_route(dept_id: int, payload: DepartmentUpdate, db: Session = Depends(get_db)):
    d = update_department(
        db,
        dept_id,
        dept_name=payload.dept_name,
        description=payload.description,
        updated_by=payload.updated_by,
    )
    db.commit()
    return d


@router.put("/sub-departments/{sub_dept_id}", response_model=SubDepartmentOut)
def update_sub_department_route(sub_dept_id: int, payload: SubDepartmentUpdate, db: Session = Depends(get_db)):
    sd = update_subdept(
        db,
        sub_dept_id,
        dept_id=payload.dept_id,
        sub_dept_name=payload.sub_dept_name,
        description=payload.description,
        updated_by=payload.updated_by,
    )
    db.commit()
    return sd


@router.put("/designations/{designation_id}", response_model=DesignationOut)
def update_designation_route(designation_id: int, payload: DesignationUpdate, db: Session = Depends(get_db)):
    des = update_designation(
        db,
        designation_id,
        designation_name=payload.designation_name,
        dept_id=payload.dept_id,
        sub_dept_id=payload.sub_dept_id,
        description=payload.description,
        updated_by=payload.updated_by,
    )
    db.commit()
    return des


# -----------------------------
# DELETE (safe; 409 on dependency)
# -----------------------------
@router.delete("/departments/{dept_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_department_route(dept_id: int, db: Session = Depends(get_db)):
    delete_department_safe(db, dept_id)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete("/sub-departments/{sub_dept_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_sub_department_route(sub_dept_id: int, db: Session = Depends(get_db)):
    delete_subdept_safe(db, sub_dept_id)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete("/designations/{designation_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_designation_route(designation_id: int, db: Session = Depends(get_db)):
    delete_designation(db, designation_id)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
