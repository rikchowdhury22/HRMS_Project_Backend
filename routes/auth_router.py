from __future__ import annotations
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Header, Request
from sqlalchemy.orm import Session
from sqlalchemy import select
from sqlalchemy.sql import false

from config import settings
from db import get_db
from models import AuthUser, Role, Employee, RefreshToken
from utils.security import (
    hash_password,
    verify_password,
    create_access_token,
    decode_access_token,
    make_refresh_token,
    refresh_exp,
    normalise_role,
    maybe_rehash_after_verify,
)

router = APIRouter(prefix="/auth", tags=["Authorization"])


# ---------- Helpers ----------
def get_role_by_name(db: Session, name: str) -> Role | None:
    return db.scalar(select(Role).where(Role.role_name == name))


def ensure_role(db: Session, name: str) -> Role:
    n = normalise_role(name)
    r = get_role_by_name(db, n)
    if not r:
        r = Role(role_name=n)
        db.add(r)
        db.commit()
        db.refresh(r)
    return r


def resolve_default_role(db: Session) -> str:
    env_default = normalise_role(getattr(settings, "DEFAULT_ROLE", None))
    if env_default and get_role_by_name(db, env_default):
        return env_default
    # fallback to EMPLOYEE if exists; else create it
    r = ensure_role(db, "EMPLOYEE")
    return r.role_name


def to_user_response(u: AuthUser) -> dict:
    e = u.Employee
    role_name = u.Role.role_name if u.Role else None
    # prefer employee full_name if available (your SQL users has no full_name)
    full_name = e.full_name if e and e.full_name else None

    return {
        "user_id": u.user_id,
        "email": u.email,
        "full_name": full_name,
        "is_active": u.is_active,
        "created_at": u.created_at,
        "updated_at": u.updated_at,
        "last_active": u.last_active,
        "role": role_name,
        "employee": (
            {
                "employee_id": e.employee_id,
                "full_name": e.full_name,
                "phone": e.phone,
                "address": e.address,
                "fathers_name": e.fathers_name,
                "aadhar_no": e.aadhar_no,
                "date_of_birth": e.date_of_birth,
                "work_position": e.work_position,
                "card_id": e.card_id,
                "dept_id": e.dept_id,
                "sub_dept_id": e.sub_dept_id,
                "designation_id": e.designation_id,
                "created_at": e.created_at,
                "updated_at": e.updated_at,
            }
            if e
            else None
        ),
    }


# ---------- Auth dependencies ----------
def get_current_user(db: Session = Depends(get_db), authorization: str = Header(None)) -> AuthUser:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Not authenticated")
    token = authorization[7:].strip()
    try:
        payload = decode_access_token(token)
        uid = int(payload["sub"])
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid or expired access token")

    u = db.get(AuthUser, uid)
    if not u or not u.is_active:
        raise HTTPException(status_code=401, detail="User not found or inactive")
    _ = u.Role, u.Employee  # eager
    return u


def require_roles(*allowed: str):
    allowed_set = {normalise_role(r) for r in allowed}

    def inner(user: AuthUser = Depends(get_current_user)):
        user_role = user.Role.role_name if user.Role else None
        if user_role not in allowed_set:
            raise HTTPException(status_code=403, detail="Forbidden")
        return user

    return inner


USERS_ENDPOINT_ALLOWED = [normalise_role(r) for r in settings.USERS_ENDPOINT_ALLOWED]
USER_GET_ENDPOINT_ALLOWED = [normalise_role(r) for r in settings.USER_GET_ENDPOINT_ALLOWED]


# ---------- Public endpoints ----------
@router.post("/register")
def register(payload: dict, db: Session = Depends(get_db)):
    email = payload.get("email")
    password = payload.get("password")
    if not (email and password):
        raise HTTPException(status_code=400, detail="email and password are required")

    exists = db.scalar(select(AuthUser).where(AuthUser.email == email))
    if exists:
        raise HTTPException(status_code=409, detail="Email already exists")

    # assign default role
    role_name = resolve_default_role(db)
    r = ensure_role(db, role_name)

    user = AuthUser(
        email=email,
        password_hash=hash_password(password),
        user_role_id=r.role_id,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    _ = user.Role, user.Employee
    return to_user_response(user)


@router.post("/login")
def login(payload: dict, request: Request, db: Session = Depends(get_db)):
    email = payload.get("email")
    password = payload.get("password")
    if not (email and password):
        raise HTTPException(status_code=400, detail="email and password are required")

    u = db.scalar(select(AuthUser).where(AuthUser.email == email))
    if not u or not verify_password(password, u.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    if (new_hash := maybe_rehash_after_verify(password, u.password_hash)):
        u.password_hash = new_hash
        db.commit()
        db.refresh(u)

    u.last_active = datetime.utcnow()
    db.commit()
    db.refresh(u)

    _ = u.Role, u.Employee
    role_name = u.Role.role_name if u.Role else None
    roles_claim = [role_name] if role_name else []
    access_token = create_access_token(str(u.user_id), roles_claim)

    rt_raw = make_refresh_token()
    new_rt = RefreshToken(
        user_id=u.user_id,
        token_hash=rt_raw["digest"],
        expires_at=refresh_exp(),
        user_agent=str(request.headers.get("user-agent") or "")[:255],
        ip=request.client.host if request.client else None,
    )
    db.add(new_rt)
    db.commit()

    return {
        "access_token": access_token,
        "refresh_token": rt_raw["raw"],
        "token_type": "bearer",
        "user": to_user_response(u),
    }


@router.get("/me")
def me(current: AuthUser = Depends(get_current_user)):
    return to_user_response(current)


@router.post("/refresh")
def refresh(payload: dict | None, request: Request, db: Session = Depends(get_db)):
    token = (payload or {}).get("refresh_token") or request.headers.get("x-refresh-token")
    if not token:
        raise HTTPException(status_code=401, detail="Missing refresh token")

    from hashlib import sha256 as _sha256
    digest = _sha256(token.encode("utf-8")).hexdigest()

    rt = db.scalar(
        select(RefreshToken).where(
            RefreshToken.token_hash == digest,
            RefreshToken.revoked == false()  # or keep == False if you prefer
        )
    )
    now = datetime.utcnow()
    if not rt or rt.expires_at <= now:
        raise HTTPException(status_code=401, detail="Invalid or expired refresh token")

    u = db.get(AuthUser, rt.user_id)
    if not u or not u.is_active:
        raise HTTPException(status_code=401, detail="User inactive or missing")

    u.last_active = datetime.utcnow()
    db.commit()

    rt.revoked = True
    db.commit()

    new_pair = make_refresh_token()
    db.add(
        RefreshToken(
            user_id=u.user_id,
            token_hash=new_pair["digest"],
            expires_at=refresh_exp(),
            user_agent=str(request.headers.get("user-agent") or "")[:255],
            ip=request.client.host if request.client else None,
        )
    )
    db.commit()

    _ = u.Role, u.Employee
    role_name = u.Role.role_name if u.Role else None
    roles_claim = [role_name] if role_name else []
    new_access = create_access_token(str(u.user_id), roles_claim)

    return {
        "access_token": new_access,
        "refresh_token": new_pair["raw"],
        "token_type": "bearer",
        "user": to_user_response(u),
    }


# ---------- Admin endpoints ----------
@router.post("/users")
def create_user(
        payload: dict,
        db: Session = Depends(get_db),
        _current: AuthUser = Depends(require_roles(*USERS_ENDPOINT_ALLOWED)),
):
    required = ["email", "password", "employee_id", "full_name"]
    missing = [k for k in required if not payload.get(k)]
    if missing:
        raise HTTPException(status_code=400, detail=f"Missing fields: {', '.join(missing)}")

    if db.scalar(select(AuthUser).where(AuthUser.email == payload["email"])):
        raise HTTPException(status_code=400, detail="Email already exists")
    if db.scalar(select(Employee).where(Employee.employee_id == payload["employee_id"])):
        raise HTTPException(status_code=400, detail="employee_id already exists")

    # role
    wanted_role = normalise_role(payload.get("role")) or resolve_default_role(db)
    r = ensure_role(db, wanted_role)

    u = AuthUser(
        email=payload["email"],
        password_hash=hash_password(payload["password"]),
        user_role_id=r.role_id,
    )
    db.add(u)
    db.commit()
    db.refresh(u)

    e = Employee(
        user_id=u.user_id,
        employee_id=payload["employee_id"],
        full_name=payload["full_name"],
        phone=payload.get("phone"),
        address=payload.get("address"),
        fathers_name=payload.get("fathers_name"),
        aadhar_no=payload.get("aadhar_no"),
        date_of_birth=payload.get("date_of_birth"),
        work_position=payload.get("work_position"),
        card_id=payload.get("card_id"),
        dept_id=payload.get("dept_id"),
        sub_dept_id=payload.get("sub_dept_id"),
        designation_id=payload.get("designation_id"),
    )
    db.add(e)
    db.commit()
    db.refresh(u)
    _ = u.Role, u.Employee
    return to_user_response(u)


@router.get("/users")
def list_users(
        q: Optional[str] = None,
        employee_id: Optional[str] = None,
        db: Session = Depends(get_db),
        _current: AuthUser = Depends(require_roles(*USERS_ENDPOINT_ALLOWED)),
):
    stmt = select(AuthUser).order_by(AuthUser.created_at.desc())
    if q:
        from sqlalchemy import or_ as _or
        stmt = stmt.where(_or(AuthUser.email.ilike(f"%{q}%")))
    rows = db.scalars(stmt).all()

    for u in rows:
        _ = u.Role, u.Employee
    if employee_id:
        rows = [u for u in rows if u.Employee and u.Employee.employee_id == employee_id]
    return [to_user_response(u) for u in rows]


@router.get("/users/{user_id}")
def get_user(
        user_id: int,
        db: Session = Depends(get_db),
        _current: AuthUser = Depends(require_roles(*USERS_ENDPOINT_ALLOWED)),
):
    u = db.get(AuthUser, user_id)
    if not u:
        raise HTTPException(status_code=404, detail="User not found")
    _ = u.Role, u.Employee
    return to_user_response(u)


@router.patch("/users/{user_id}")
def patch_user(
        user_id: int,
        payload: dict,
        db: Session = Depends(get_db),
        _current: AuthUser = Depends(require_roles(*USER_GET_ENDPOINT_ALLOWED)),
):
    u = db.get(AuthUser, user_id)
    if not u:
        raise HTTPException(status_code=404, detail="User not found")

    # toggle active
    if "is_active" in payload:
        u.is_active = bool(payload["is_active"])

    # update employee subset if exists
    if u.Employee:
        e = u.Employee
        for field in ["full_name", "phone", "address", "fathers_name", "aadhar_no",
                      "date_of_birth", "work_position", "card_id",
                      "dept_id", "sub_dept_id", "designation_id"]:
            if field in payload:
                setattr(e, field, payload[field])

    db.commit()
    db.refresh(u)
    _ = u.Role, u.Employee
    return to_user_response(u)

@router.get("/members")
def list_members_by_department(
    dept_id: int,
    role: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
    db: Session = Depends(get_db),
    _current: AuthUser = Depends(get_current_user),  # any authenticated user
):
    """
    Return members under a department with minimal fields:
    - email, full_name, phone, dept_id
    Optional filter: role (any role string; case/space-insensitive)
    """
    role_norm = normalise_role(role) if role else None

    # Base join: Users -> Employee (must have employee row and the given department)
    # (AuthUser) INNER JOIN (Employee) on user_id
    stmt = (
        select(
            AuthUser.email,
            Employee.full_name,
            Employee.phone,
            Employee.dept_id,
        )
        .join(Employee, Employee.user_id == AuthUser.user_id)
        .where(Employee.dept_id == dept_id)
        .order_by(Employee.full_name.asc())
        .limit(limit)
        .offset(offset)
    )

    # Optional role filter (Users -> Role)
    if role_norm:
        stmt = stmt.join(Role, Role.role_id == AuthUser.user_role_id).where(Role.role_name == role_norm)

    rows = db.execute(stmt).all()

    return [
        {
            "email": r[0],
            "full_name": r[1],
            "phone": r[2],
            "dept_id": r[3],
        }
        for r in rows
    ]

@router.patch("/me/profile")
def upsert_my_profile(
    payload: dict,
    db: Session = Depends(get_db),
    current: AuthUser = Depends(get_current_user),
):
    """
    Create or update the current user's Employee profile.
    - If Employee doesn't exist: requires employee_id and full_name.
    - Otherwise partial updates are allowed.
    Fields accepted:
      employee_id (required on create), full_name, phone, address, fathers_name,
      aadhar_no, date_of_birth (YYYY-MM-DD), work_position, card_id,
      dept_id, sub_dept_id, designation_id, profile_photo
    """
    u = current
    e = u.Employee

    creating = e is None
    if creating:
        # Validate create requirements
        employee_id = payload.get("employee_id")
        full_name = payload.get("full_name")
        if not employee_id or not full_name:
            raise HTTPException(status_code=400, detail="employee_id and full_name are required to create a profile")

        # Ensure unique employee_id
        exists_empid = db.scalar(select(Employee).where(Employee.employee_id == employee_id))
        if exists_empid:
            raise HTTPException(status_code=409, detail="employee_id already exists")

        e = Employee(
            user_id=u.user_id,
            employee_id=employee_id,
            full_name=full_name,
            phone=payload.get("phone"),
            address=payload.get("address"),
            fathers_name=payload.get("fathers_name"),
            aadhar_no=payload.get("aadhar_no"),
            date_of_birth=payload.get("date_of_birth"),
            work_position=payload.get("work_position"),
            card_id=payload.get("card_id"),
            dept_id=payload.get("dept_id"),
            sub_dept_id=payload.get("sub_dept_id"),
            designation_id=payload.get("designation_id"),
            profile_photo=payload.get("profile_photo"),
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        db.add(e)
        db.commit()
        db.refresh(u)  # refresh relationships
        _ = u.Employee
        return to_user_response(u)

    # UPDATE (partial)
    updatable_fields = [
        "employee_id",         # allow changing with uniqueness check
        "full_name", "phone", "address", "fathers_name", "aadhar_no",
        "date_of_birth", "work_position", "card_id",
        "dept_id", "sub_dept_id", "designation_id",
        "profile_photo",
    ]

    # If employee_id is provided for update, ensure it's unique
    if "employee_id" in payload and payload["employee_id"] and payload["employee_id"] != e.employee_id:
        conflict = db.scalar(select(Employee).where(Employee.employee_id == payload["employee_id"]))
        if conflict:
            raise HTTPException(status_code=409, detail="employee_id already exists")
        e.employee_id = payload["employee_id"]

    for f in updatable_fields:
        if f in payload and f != "employee_id":
            setattr(e, f, payload[f])

    e.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(u)
    _ = u.Employee
    return to_user_response(u)

@router.get("/roles")
def list_roles(
    q: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
    db: Session = Depends(get_db),
    _current: AuthUser = Depends(require_roles("SUPER-ADMIN", "ADMIN")),  # any authenticated user
):
    """
    List roles from dbo.role_list.
    - Optional text search by role_name/description: ?q=admin
    - Pagination: ?limit=50&offset=0
    """
    stmt = select(Role).order_by(Role.role_name.asc()).limit(limit).offset(offset)
    if q:
        from sqlalchemy import or_ as _or
        like = f"%{q}%"
        stmt = (
            select(Role)
            .where(_or(Role.role_name.ilike(like), Role.description.ilike(like)))
            .order_by(Role.role_name.asc())
            .limit(limit)
            .offset(offset)
        )

    roles = db.scalars(stmt).all()
    return [
        {
            "role_id": r.role_id,
            "role_name": r.role_name,
            "description": r.description,
        }
        for r in roles
    ]
