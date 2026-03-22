from fastapi import APIRouter
from app.api.health import router as health_router
from app.api.auth import router as auth_router
from app.api.users import router as users_router
from app.api.icp import router as icp_router
from app.api.pipeline import router as pipeline_router
from app.api.leads import router as leads_router
from app.api.chat import router as chat_router
from app.api.tools import router as tools_router
from app.api.admin import router as admin_router
from app.api.knowledge_base import router as kb_router

api_router = APIRouter()

api_router.include_router(health_router)
api_router.include_router(auth_router)
api_router.include_router(users_router)
api_router.include_router(icp_router)
api_router.include_router(pipeline_router)
api_router.include_router(leads_router)
api_router.include_router(chat_router)
api_router.include_router(tools_router)
api_router.include_router(admin_router)
api_router.include_router(kb_router)
