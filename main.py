# main.py
from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import text

from config import settings
from db import get_db, ping_db, SessionLocal
from routes import api_router
from routes import org_router
from db import engine, Base
from models import projects

# Router presence flag (kept from your code)
try:
    from routes import api_router
    from routes import org_router

    ROUTERS_PRESENT = True
except Exception:
    ROUTERS_PRESENT = False

app = FastAPI(title="HRMS Backend - 1: APIs", version="0.0.1")

# CORS (open; tighten later)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# include all routers
if ROUTERS_PRESENT:
    app.include_router(api_router)
    app.include_router(org_router)


@app.on_event("startup")
def _startup():
    print("🚀 Starting FastAPI Server...")
    print(f"🔗 MSSQL: {settings.DB_HOST}:{settings.DB_PORT}")
    try:
        ping_db()
        print("✅ Database connection OK.")
    except SQLAlchemyError as e:
        print("❌ Database connection failed:", e)
        return

    if ROUTERS_PRESENT:
        print("🧩 Routers loaded from routes/")

    # ---- seed super admin (idempotent, SQL-only) ----
    # try:
    #     with SessionLocal() as db:
    #         result = seed_super_admin_sql(db)
    #         print(f"🌱 Seeded Super Admin: {result}")
    # except Exception as e:
    #     print("⚠️ Super Admin seed failed:", e)

    print("✅ Startup complete.\n")
    
    Base.metadata.create_all(bind=engine)


@app.get("/health")
def health():
    return {"status": "ok", "version": "0.1.0"}


@app.get("/db/ping")
def db_ping():
    ping_db()
    return {"db": "up"}


@app.get("/example-now", summary="Simple sample query to prove the session works")
def example_now(db: Session = Depends(get_db)):
    row = db.execute(text("SELECT SYSDATETIMEOFFSET() AS now_utc_offset")).fetchone()
    return {"now": str(row.now_utc_offset) if row else None}


@app.get("/whoami", summary="Stub endpoint—plug JWT later")
def whoami():
    return {
        "allowed_users_endpoints": settings.USERS_ENDPOINT_ALLOWED,
        "allowed_user_get_endpoints": settings.USER_GET_ENDPOINT_ALLOWED,
        "note": "JWT/roles enforced by auth_router where applied.",
    }
