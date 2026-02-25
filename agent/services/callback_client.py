import httpx
import structlog

from models import Lead

logger = structlog.get_logger()

MAX_RETRIES = 3


async def send_callback(
    callback_url: str,
    job_id: str,
    status: str,
    leads: list[Lead] | None = None,
    error: str | None = None,
) -> None:
    """Send final results back to the Spring Boot backend."""
    payload = {
        "jobId": job_id,
        "status": status,
        "leads": [lead.model_dump(by_alias=True) for lead in (leads or [])],
    }
    if error:
        payload["error"] = error

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.post(callback_url, json=payload)
                response.raise_for_status()
                logger.info(
                    "callback_sent",
                    job_id=job_id,
                    status=status,
                    lead_count=len(leads) if leads else 0,
                )
                return
        except Exception as e:
            logger.warning(
                "callback_failed",
                job_id=job_id,
                attempt=attempt,
                error=str(e),
            )
            if attempt == MAX_RETRIES:
                logger.error("callback_exhausted", job_id=job_id, error=str(e))
                raise
