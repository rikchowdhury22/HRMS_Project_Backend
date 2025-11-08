# routes/scrum_router.py
from __future__ import annotations
from datetime import datetime, timezone, time
from typing import Optional, List

from fastapi import APIRouter, HTTPException, Query, status, Depends
from sqlalchemy.orm import Session
from sqlalchemy import select

from db import get_db
from mongo import scrum_col
from models.sub_projects import SubProject
from schemas.scrum import ScrumCreate, ScrumUpdate, ScrumOut

router = APIRouter(prefix="/scrums", tags=["Daily Scrum"])
UTC = timezone.utc

# ---------- Helpers ----------
def _now_utc() -> datetime:
    return datetime.now(UTC)


def _doc_to_out(d: dict) -> ScrumOut:
    eta_raw = d.get("eta_date")
    eta_as_date = eta_raw.date() if isinstance(eta_raw, datetime) else eta_raw
    return ScrumOut(
        id=str(d["_id"]),
        subproject_id=int(d["subproject_id"]),
        user_id=int(d["user_id"]),
        today_task=d["today_task"],
        eta_date=eta_as_date,
        dependencies=d.get("dependencies"),  # ✅ new structure
        concern=d.get("concern"),
        created_at=d["created_at"],
    )


# ---------- ROUTES ----------
@router.get("", response_model=List[ScrumOut])
def list_scrums(
    db: Session = Depends(get_db),
    subproject_id: Optional[int] = None,
    user_id: Optional[int] = None,
    date_from: Optional[str] = Query(None, description="UTC date YYYY-MM-DD"),
    date_to: Optional[str] = Query(None, description="UTC date YYYY-MM-DD inclusive"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    q = {}
    if subproject_id is not None:
        q["subproject_id"] = int(subproject_id)
    if user_id is not None:
        q["user_id"] = int(user_id)

    if date_from or date_to:
        from datetime import datetime as _dt
        rng = {}
        if date_from:
            rng["$gte"] = _dt.fromisoformat(date_from).replace(tzinfo=UTC)
        if date_to:
            to = _dt.fromisoformat(date_to).replace(
                hour=23, minute=59, second=59, microsecond=999999, tzinfo=UTC
            )
            rng["$lte"] = to
        q["created_at"] = rng

    docs = list(scrum_col.find(q).sort("created_at", -1).skip(offset).limit(limit))
    return [_doc_to_out(d) for d in docs]


@router.post("", response_model=ScrumOut, status_code=status.HTTP_201_CREATED)
def create_scrum(payload: ScrumCreate, db: Session = Depends(get_db)):
    # Validate subproject exists in SQL
    exists_id = db.scalar(
        select(SubProject.subproject_id).where(SubProject.subproject_id == payload.subproject_id)
    )
    if not exists_id:
        raise HTTPException(status_code=404, detail="Sub-project not found")

    now = _now_utc()
    eta_dt = datetime.combine(payload.eta_date, time(0, 0, 0), tzinfo=UTC)

    doc = {
        "subproject_id": int(payload.subproject_id),
        "user_id": int(payload.user_id),
        "today_task": payload.today_task.strip(),
        "eta_date": eta_dt,
        "dependencies": [dep.model_dump() for dep in (payload.dependencies or [])],  # ✅
        "concern": (payload.concern.strip() if payload.concern else None),
        "created_at": now,
    }

    res = scrum_col.insert_one(doc)
    doc["_id"] = res.inserted_id
    return _doc_to_out(doc)


# ✅ GET latest scrum where user is owner OR dependency user
@router.get("/user/{user_id}", response_model=ScrumOut)
def get_scrum_by_user(user_id: int):
    query = {
        "$or": [
            {"user_id": int(user_id)},
            {"dependencies": {"$elemMatch": {"user_id": int(user_id)}}},  # ✅ new structure query
        ]
    }
    cursor = scrum_col.find(query).sort("created_at", -1).limit(1)
    docs = list(cursor)
    if not docs:
        raise HTTPException(status_code=404, detail="No scrum found for this user")
    return _doc_to_out(docs[0])


# ✅ PUT latest scrum where user is owner OR dependency user
@router.put("/user/{user_id}", response_model=ScrumOut)
def update_scrum_by_user(user_id: int, payload: ScrumUpdate):
    query = {
        "$or": [
            {"user_id": int(user_id)},
            {"dependencies": {"$elemMatch": {"user_id": int(user_id)}}},  # ✅
        ]
    }
    cursor = scrum_col.find(query).sort("created_at", -1).limit(1)
    docs = list(cursor)
    if not docs:
        raise HTTPException(status_code=404, detail="No scrum found for this user")

    target = docs[0]
    patch = {}
    if payload.today_task is not None:
        patch["today_task"] = payload.today_task.strip()
    if payload.eta_date is not None:
        patch["eta_date"] = datetime.combine(payload.eta_date, time(0, 0, 0), tzinfo=UTC)
    if payload.dependencies is not None:
        patch["dependencies"] = [dep.model_dump() for dep in payload.dependencies]  # ✅
    if payload.concern is not None:
        patch["concern"] = payload.concern.strip() if payload.concern else None

    if not patch:
        return _doc_to_out(target)

    scrum_col.update_one({"_id": target["_id"]}, {"$set": patch})
    new_doc = scrum_col.find_one({"_id": target["_id"]})
    return _doc_to_out(new_doc)
