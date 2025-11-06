# db.py
from __future__ import annotations

import os
from urllib.parse import quote_plus
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, declarative_base

# Optional but useful: fail fast if the ODBC driver is not installed
try:
    import pyodbc  # ensure available in the venv
    _AVAILABLE_DRIVERS = {d.strip() for d in pyodbc.drivers()}
except Exception:
    _AVAILABLE_DRIVERS = set()

from config import settings


def _build_odbc_connection_string() -> str:
    """
    Returns a full ODBC connection string suitable for pyodbc.
    We will wrap this with quote_plus and feed it via odbc_connect.
    """
    driver = os.getenv("DB_DRIVER", "ODBC Driver 18 for SQL Server")
    host = settings.DB_HOST
    port = settings.DB_PORT
    db   = settings.DB_NAME
    user = settings.DB_USER
    pwd  = settings.DB_PASSWORD

    encrypt = "yes" if settings.DB_ENCRYPT else "no"
    trust   = "yes" if settings.DB_TRUST_SERVER_CERT else "no"

    # Sanity check: give a clear message if driver is missing
    if _AVAILABLE_DRIVERS and driver not in _AVAILABLE_DRIVERS:
        raise RuntimeError(
            f"Configured DB_DRIVER '{driver}' not found. "
            f"Installed drivers: {sorted(_AVAILABLE_DRIVERS)}. "
            f"Install the correct Microsoft ODBC Driver (e.g., 18) "
            f"or set DB_DRIVER accordingly."
        )

    # If you use a named instance, you can set DB_HOST like 'MACHINE\\SQLEXPRESS'
    # For TCP with explicit port, keep SERVER=host,port
    odbc = (
        f"DRIVER={{{driver}}};"
        f"SERVER={host},{port};"
        f"DATABASE={db};"
        f"UID={user};PWD={pwd};"
        f"Encrypt={encrypt};"
        f"TrustServerCertificate={trust};"
    )
    return odbc


def _build_sqlalchemy_url() -> str:
    # Quote the entire ODBC string; this handles special characters safely
    odbc = _build_odbc_connection_string()
    return "mssql+pyodbc:///?odbc_connect=" + quote_plus(odbc)


engine = create_engine(
    _build_sqlalchemy_url(),
    pool_pre_ping=True,
    pool_recycle=1800,
    echo=settings.DB_ENABLE_LOG,
    future=True,
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)

Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def ping_db() -> bool:
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
    return True
