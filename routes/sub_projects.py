from config import settings
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import select
from db import get_db
from models.sub_projects import SubProject
from schemas.sub_projects import SubProjectCreate, SubProjectUpdate, SubProjectOut
from datetime import datetime
from routes.auth_router import get_current_user, require_roles

router = APIRouter(prefix="/sub-projects", tags=["Sub-Projects"])

# ---- guards (toggleable) ----
if settings.AUTH_DISABLED:
    async def _noop():
        return None
    AUTH_GUARD = Depends(_noop)
    WRITE_GUARD = Depends(_noop)
else:
    AUTH_GUARD = Depends(get_current_user)
    WRITE_GUARD = Depends(require_roles("SUPER-ADMIN", "ADMIN", "MANAGER"))

def _paginate(q, page: int, page_size: int):
    return q.offset((page - 1) * page_size).limit(page_size)

@router.get("", response_model=List[SubProjectOut])
def list_subprojects(
    db: Session = Depends(get_db),
    _u = AUTH_GUARD,
    project_id: Optional[int] = None,
    status_filter: Optional[str] = Query(None, alias="status"),
    user_id: Optional[int] = None,                 # 🔹 new optional filter
    page: int = 1,
    page_size: int = 50,
):
    stmt = select(SubProject)

    if project_id is not None:
        stmt = stmt.where(SubProject.project_id == project_id)

    if status_filter:
        stmt = stmt.where(SubProject.project_status == status_filter)

    # 🔹 Filter by assigned_to user, if provided
    if user_id is not None:
        stmt = stmt.where(SubProject.assigned_to == user_id)

    stmt = stmt.order_by(SubProject.subproject_id.desc())
    return db.execute(_paginate(stmt, page, page_size)).scalars().all()


@router.get("/{subproject_id}", response_model=SubProjectOut)
def get_subproject(subproject_id: int, db: Session = Depends(get_db), _u = AUTH_GUARD):
    obj = db.get(SubProject, subproject_id)
    if not obj:
        raise HTTPException(404, "Sub-project not found")
    return obj


@router.post("", response_model=SubProjectOut, status_code=201)
def create_subproject(payload: SubProjectCreate, db: Session = Depends(get_db), _ = WRITE_GUARD):
    data = payload.model_dump(exclude_unset=True, exclude_none=True)  # ✅ prevents sending None
    obj = SubProject(**data)
    db.add(obj)
    try:
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(409, f"Insert failed: {e}")
    db.refresh(obj)
    return obj


@router.put("/{subproject_id}", response_model=SubProjectOut)
def update_subproject(subproject_id: int, payload: SubProjectUpdate, db: Session = Depends(get_db), _ = WRITE_GUARD):
    obj = db.get(SubProject, subproject_id)
    if not obj:
        raise HTTPException(404, "Sub-project not found")

    for k, v in payload.model_dump(exclude_none=True).items():
        setattr(obj, k, v)

    # ✅ Add this line
    obj.last_modified = datetime.utcnow()

    try:
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(409, f"Update failed: {e}")

    db.refresh(obj)
    return obj

@router.delete("/{subproject_id}", status_code=204)
def delete_subproject(subproject_id: int, db: Session = Depends(get_db), _ = WRITE_GUARD):
    obj = db.get(SubProject, subproject_id)
    if not obj:
        return
    db.delete(obj)
    try:
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(409, f"Delete failed: {e}")
