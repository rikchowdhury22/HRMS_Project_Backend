# routes/scrum_router.py
from __future__ import annotations
from datetime import datetime, timezone, timedelta, time
from typing import Optional, List, Literal

from fastapi import APIRouter, HTTPException, Query, status, Depends, Body
from sqlalchemy.orm import Session
from sqlalchemy import select

from db import get_db
from mongo import scrum_col
from models.sub_projects import SubProject
from schemas.scrum import ScrumCreate, ScrumUpdate, ScrumOut, ScrumOutWithHours, ScrumLifecycleAction
from bson import ObjectId

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
        dependencies=d.get("dependencies"),
        concern=d.get("concern"),
        created_at=d["created_at"],
        scrum_status=d.get("scrum_status", "Planned"),   # NEW
        last_action_at=d.get("last_action_at"),          # NEW
        status_events=d.get("status_events"),            # NEW
    )

def _auto_pause_others(user_id: int, current_scrum_oid: ObjectId, actor_id: int | None):
    """
    Pauses any other Running scrums for the user using a single pipeline update.
    Uses $$NOW so 'scrum_status', 'last_action_at', and the appended event share the same timestamp.
    """
    scrum_col.update_many(
        {
            "user_id": user_id,
            "scrum_status": "Running",
            "_id": {"$ne": current_scrum_oid},
        },
        [
            # 1) set status + last_action_at using the same server time
            {"$set": {
                "scrum_status": "Paused",
                "last_action_at": "$$NOW"
            }},
            # 2) append an event atomically (concat existing or empty with new element)
            {"$set": {
                "status_events": {
                    "$concatArrays": [
                        {"$ifNull": ["$status_events", []]},
                        [{
                            "status": "Paused",
                            "note": "Auto-paused due to new start",
                            "actor_id": actor_id,
                            "at": "$$NOW"
                        }]
                    ]
                }
            }},
        ],
    )


def _transition_with_event(scrum_oid: ObjectId, new_status: str, note: str | None, actor_id: int | None):
    """
    Transitions one scrum to new_status and appends an audit event using a single pipeline update.
    """
    scrum_col.update_one(
        {"_id": scrum_oid},
        [
            {"$set": {
                "scrum_status": new_status,
                "last_action_at": "$$NOW"
            }},
            {"$set": {
                "status_events": {
                    "$concatArrays": [
                        {"$ifNull": ["$status_events", []]},
                        [{
                            "status": new_status,
                            "note": note,
                            "actor_id": actor_id,
                            "at": "$$NOW"
                        }]
                    ]
                }
            }},
        ],
    )

def calculate_scrum_work_hours(scrum_doc: dict) -> float:
    """
    Returns total working hours (float, in hours) for a single scrum document
    based on its status_events list.
    """
    events = sorted(scrum_doc.get("status_events", []), key=lambda e: e.get("at"))
    total = timedelta()

    start_time = None
    for ev in events:
        st = ev.get("status")
        ts = ev.get("at")
        if not ts:
            continue
        # normalize to datetime
        if isinstance(ts, str):
            ts = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        if st == "Running":
            start_time = ts
        elif st in ("Paused", "Completed") and start_time:
            total += ts - start_time
            start_time = None
    # convert to hours (float)
    return round(total.total_seconds() / 3600, 2)

# ---------- ROUTES ----------

@router.get("", response_model=List[ScrumOutWithHours])
def list_scrums(
    db: Session = Depends(get_db),
    subproject_id: Optional[int] = None,
    user_id: Optional[int] = None,
    date_from: Optional[str] = Query(None, description="UTC date YYYY-MM-DD"),
    date_to: Optional[str] = Query(None, description="UTC date YYYY-MM-DD inclusive"),
    include_hours: bool = Query(False, description="Include calculated work hours per scrum"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    """
    Unified endpoint:
    - No filters  -> all scrums
    - user_id     -> filter by user
    - subproject_id -> filter by subproject
    - date_from/date_to (UTC) -> filter by created_at
    - include_hours=true -> adds 'work_hours' to each record
    - limit/offset -> pagination
    """
    q: dict = {}

    if subproject_id is not None:
        q["subproject_id"] = int(subproject_id)
    if user_id is not None:
        q["user_id"] = int(user_id)

    if date_from or date_to:
        rng = {}
        if date_from:
            rng["$gte"] = datetime.fromisoformat(date_from).replace(tzinfo=UTC)
        if date_to:
            rng["$lte"] = datetime.fromisoformat(date_to).replace(
                hour=23, minute=59, second=59, microsecond=999999, tzinfo=UTC
            )
        q["created_at"] = rng

    docs = list(
        scrum_col.find(q)
        .sort("created_at", -1)
        .skip(offset)
        .limit(limit)
    )

    results: List[ScrumOutWithHours] = []
    for d in docs:
        out = _doc_to_out(d)  # returns ScrumOut-compatible object
        # coerce to ScrumOutWithHours (Pydantic will accept the superset)
        out = ScrumOutWithHours(**out.model_dump())
        if include_hours:
            out.work_hours = calculate_scrum_work_hours(d)
        results.append(out)

    return results


@router.post("", response_model=ScrumOut, status_code=status.HTTP_201_CREATED)
def create_scrum(payload: ScrumCreate, db: Session = Depends(get_db)):
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
        "dependencies": [dep.model_dump() for dep in (payload.dependencies or [])],
        "concern": (payload.concern.strip() if payload.concern else None),
        "created_at": now,
        "scrum_status": "Planned",      
    }

    res = scrum_col.insert_one(doc)
    doc["_id"] = res.inserted_id
    return _doc_to_out(doc)


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



# ---------- SCRUM LIFECYCLE ----------

@router.post("/{scrum_id}/lifecycle", response_model=ScrumOut)
def mutate_scrum_lifecycle(
    scrum_id: str,
    payload: ScrumLifecycleAction = Body(...),
):
    """
    Unified lifecycle endpoint:
    - action: 'start' | 'pause' | 'end'
    - note, actor_id: optional audit fields
    Behavior:
      • 'start' auto-pauses any other Running scrum(s) for the same user (audit logged)
      • all transitions are atomic and stamped with Mongo $$NOW
    """
    doc = scrum_col.find_one({"_id": ObjectId(scrum_id)})
    if not doc:
        raise HTTPException(404, "Scrum not found")

    current = doc.get("scrum_status", "Planned")
    action = payload.action
    note = payload.note
    actor_id = payload.actor_id

    if action == "start":
        if current == "Running":
            raise HTTPException(400, "Scrum already running")
        if current == "Completed":
            raise HTTPException(400, "Cannot start a completed scrum")

        # Auto-pause any other running scrums for this user
        _auto_pause_others(user_id=doc["user_id"], current_scrum_oid=doc["_id"], actor_id=actor_id)
        # Transition this one to Running with audit event
        _transition_with_event(scrum_oid=doc["_id"], new_status="Running", note=note, actor_id=actor_id)

    elif action == "pause":
        if current != "Running":
            raise HTTPException(400, "Scrum is not running")
        _transition_with_event(scrum_oid=doc["_id"], new_status="Paused", note=note, actor_id=actor_id)

    elif action == "end":
        if current == "Completed":
            raise HTTPException(400, "Scrum already completed")
        _transition_with_event(scrum_oid=doc["_id"], new_status="Completed", note=note, actor_id=actor_id)

    else:
        raise HTTPException(422, "Invalid action")

    updated = scrum_col.find_one({"_id": doc["_id"]})
    return _doc_to_out(updated)
