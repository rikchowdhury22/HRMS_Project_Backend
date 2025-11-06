from fastapi import APIRouter
from .auth_router import router as auth_router
from .org import router as org_router
from .projects import router as projects_router
from .sub_projects import router as subprojects_router

api_router = APIRouter()
api_router.include_router(auth_router)
api_router.include_router(org_router)
api_router.include_router(projects_router)
api_router.include_router(subprojects_router)
