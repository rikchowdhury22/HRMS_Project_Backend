# routes/__init__.py
from __future__ import annotations
from fastapi import APIRouter

from .auth_router import router as auth_router
from .org_router import router as org_router

api_router = APIRouter()
api_router.include_router(auth_router)
api_router.include_router(org_router)
