import httpx
import structlog

from config import settings

logger = structlog.get_logger()


async def report_progress(job_id: str, stage: str, message: str, progress: int) -> None:
    """Send a progress update to the backend."""
    url = f"{settings.backend_callback_base_url}/api/v1/internal/jobs/{job_id}/progress"
    payload = {
        "jobId": job_id,
        "stage": stage,
        "message": message,
        "progress": progress,
    }

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.post(url, json=payload)
            response.raise_for_status()
            logger.info("progress_reported", job_id=job_id, stage=stage, progress=progress)
    except Exception as e:
        logger.warning("progress_report_failed", job_id=job_id, stage=stage, error=str(e))
