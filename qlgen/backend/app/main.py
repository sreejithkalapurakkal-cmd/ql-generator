import os
import logging
from pathlib import Path
from dotenv import load_dotenv

logging.basicConfig(level=logging.INFO)

# Load .env from project root
env_path = Path(__file__).resolve().parent.parent.parent / ".env"
load_dotenv(env_path)

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.router import api_router
from app.config import get_settings

settings = get_settings()

app = FastAPI(title="qlGen API", version="1.0.0", description="ICP-Driven Qualified Lead Generation Tool")

origins = [o.strip() for o in settings.CORS_ALLOWED_ORIGINS.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix="/api/v1")

# Observability middleware (request timing, request_id, structured logging)
from app.middleware.observability import ObservabilityMiddleware, get_metrics
app.add_middleware(ObservabilityMiddleware)


@app.get("/")
async def root():
    return {"message": "qlGen API is running", "docs": "/docs"}


@app.get("/health/metrics")
async def health_metrics():
    """Operational metrics: uptime, request count, latency, top endpoints."""
    return get_metrics()
