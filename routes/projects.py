from config import settings
from datetime import datetime
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import select

from db import get_db
from models.projects import Project                      # ← keep this if your file is models/projects.py
from models.project_members import ProjectMember
from schemas.projects import ProjectCreate, ProjectUpdate, ProjectOut
from schemas.project_members import ProjectMemberCreate, ProjectMemberOut
from routes.auth_router import get_current_user, require_roles

router= APIRouter(prefix="/projects", tags=["Projects"])

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


@router.get("", response_model=List[ProjectOut])
def list_projects(
    db: Session = Depends(get_db),
    _u = AUTH_GUARD,
    q: Optional[str] = Query(None),
    status_filter: Optional[str] = Query(None, alias="status"),
    created_by: Optional[int] = None,
    page: int = 1,
    page_size: int = 50,
):
    stmt = select(Project)
    if q:
        stmt = stmt.where(Project.project_name.ilike(f"%{q}%"))
    if status_filter:
        stmt = stmt.where(Project.project_status == status_filter)
    if created_by is not None:
        stmt = stmt.where(Project.created_by == created_by)
    stmt = stmt.order_by(Project.project_id.desc())
    return db.execute(_paginate(stmt, page, page_size)).scalars().all()

@router.get("/{project_id}", response_model=ProjectOut)
def get_project(project_id: int, db: Session = Depends(get_db), _u = AUTH_GUARD):
    obj = db.get(Project, project_id)
    if not obj:
        raise HTTPException(404, "Project not found")
    return obj

@router.post("", response_model=ProjectOut, status_code=status.HTTP_201_CREATED)
def create_project(payload: ProjectCreate, db: Session = Depends(get_db), _ = WRITE_GUARD):
    obj = Project(**payload.model_dump())

    # Defensive fallback if DB defaults aren’t wired yet
    if not getattr(obj, "created_on", None):
        obj.created_on = datetime.utcnow()
    if not getattr(obj, "last_modified", None):
        obj.last_modified = datetime.utcnow()

    db.add(obj)
    try:
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(409, f"Insert failed: {e}")
    db.refresh(obj)
    return obj

@router.put("/{project_id}", response_model=ProjectOut)
def update_project(project_id: int, payload: ProjectUpdate, db: Session = Depends(get_db), _=WRITE_GUARD):
    obj = db.get(Project, project_id)
    if not obj:
        raise HTTPException(status_code=404, detail="Project not found")

    patch = payload.model_dump(exclude_unset=True)
    for k, v in patch.items():
        setattr(obj, k, v)

    db.commit()      # DB onupdate/trigger should bump last_modified
    db.refresh(obj)
    return obj

@router.delete("/{project_id}", status_code=204)
def delete_project(project_id: int, db: Session = Depends(get_db), _ = WRITE_GUARD):
    obj = db.get(Project, project_id)
    if not obj:
        return
    db.delete(obj)
    try:
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(409, f"Delete failed: {e}")

# ----- Members -----
@router.get("/{project_id}/members", response_model=List[ProjectMemberOut])
def list_members(project_id: int, db: Session = Depends(get_db), _u = AUTH_GUARD):
    stmt = select(ProjectMember).where(ProjectMember.project_id == project_id)
    return db.execute(stmt).scalars().all()

@router.post("/{project_id}/members", response_model=ProjectMemberOut, status_code=201)
def add_member(project_id: int, payload: ProjectMemberCreate, db: Session = Depends(get_db), _ = WRITE_GUARD):
    if not db.get(Project, project_id):
        raise HTTPException(404, "Project not found")
    m = ProjectMember(project_id=project_id, **payload.model_dump())
    db.add(m)
    try:
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(409, f"Add member failed: {e}")
    db.refresh(m)
    return m

@router.delete("/{project_id}/members/{user_id}", status_code=204)
def remove_member(project_id: int, user_id: int, db: Session = Depends(get_db), _ = WRITE_GUARD):
    m = db.get(ProjectMember, (project_id, user_id))  # tuple for composite PK
    if not m:
        return
    db.delete(m)
    try:
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(409, f"Remove member failed: {e}")
