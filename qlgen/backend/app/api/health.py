from fastapi import APIRouter

from app.middleware.observability import get_metrics

router = APIRouter()


@router.get("/health")
async def health_check():
    return {"status": "healthy", "service": "qlGen API"}


@router.get("/health/metrics")
async def health_metrics():
    """Return collected observability metrics (counters, histograms, request stats)."""
    return get_metrics()
