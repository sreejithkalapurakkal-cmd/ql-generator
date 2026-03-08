from fastapi import APIRouter
from app.api.health import router as health_router
from app.api.icp import router as icp_router
from app.api.pipeline import router as pipeline_router
from app.api.leads import router as leads_router
from app.api.chat import router as chat_router

api_router = APIRouter()

api_router.include_router(health_router)
api_router.include_router(icp_router)
api_router.include_router(pipeline_router)
api_router.include_router(leads_router)
api_router.include_router(chat_router)
