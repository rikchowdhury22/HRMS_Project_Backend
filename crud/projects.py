# crud/projects.py
from sqlalchemy.orm import Session
from models.projects import Project
from schemas.projects import ProjectCreate

def create_project(db: Session, payload: ProjectCreate) -> Project:
    # pydantic v2 uses .model_dump(); v1 uses .dict()
    data = payload.model_dump() if hasattr(payload, "model_dump") else payload.dict()
    obj = Project(**data)
    db.add(obj)
    db.commit()
    db.refresh(obj)  # pulls DB-generated created_on/last_modified
    return obj

def update_project(db: Session, project_id: int, patch: dict) -> Project:
    obj = db.get(Project, project_id)
    if not obj:
        return None
    for k, v in patch.items():
        setattr(obj, k, v)
    db.commit()      # onupdate + (optional trigger) updates last_modified
    db.refresh(obj)
    return obj
