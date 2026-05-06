from datetime import date, datetime, timezone

import requests
from prefect import flow, task

from shared.config import load_config
from shared.logger import get_logger
from shared.models import HeavyPipelineResult

logger = get_logger(__name__)

HEALTH_CHECK_TIMEOUT = 10
PROCESS_TIMEOUT = 300  # 5 minutes


@task(name="check-heavy-worker-health", retries=3, retry_delay_seconds=[5, 10, 20])
def check_heavy_worker_health(heavy_worker_url: str) -> None:
    url = f"{heavy_worker_url}/health"
    logger.info("checking_heavy_worker_health", url=url)

    try:
        response = requests.get(url, timeout=HEALTH_CHECK_TIMEOUT)
        response.raise_for_status()
    except requests.RequestException as exc:
        logger.error("heavy_worker_unavailable", url=url, error=str(exc))
        raise

    logger.info("heavy_worker_healthy", url=url)


@task(name="trigger-heavy-processing", retries=1, retry_delay_seconds=30)
def trigger_heavy_processing(
    heavy_worker_url: str, process_date: str
) -> HeavyPipelineResult:
    url = f"{heavy_worker_url}/process"
    payload = {"date": process_date}

    logger.info("triggering_heavy_processing", url=url, date=process_date)

    try:
        response = requests.post(url, json=payload, timeout=PROCESS_TIMEOUT)
        response.raise_for_status()
    except requests.Timeout:
        logger.error(
            "heavy_processing_timeout",
            url=url,
            date=process_date,
            timeout=PROCESS_TIMEOUT,
        )
        raise
    except requests.RequestException as exc:
        logger.error(
            "heavy_processing_failed", url=url, date=process_date, error=str(exc)
        )
        raise

    data = response.json()
    result = HeavyPipelineResult(
        courses_processed=data["courses_processed"],
        alerts_generated=data["alerts_generated"],
        date=data["date"],
    )

    logger.info(
        "heavy_processing_completed",
        courses_processed=result.courses_processed,
        alerts_generated=result.alerts_generated,
        date=result.date,
    )
    return result


@flow(name="heavy-pipeline", log_prints=False)
def run_heavy_pipeline(process_date: str | None = None) -> None:
    config = load_config()
    target_date = process_date or date.today().isoformat()

    logger.info("heavy_pipeline_started", date=target_date)

    check_heavy_worker_health(config.heavy_worker_url)
    result = trigger_heavy_processing(config.heavy_worker_url, target_date)

    logger.info(
        "heavy_pipeline_completed",
        courses_processed=result.courses_processed,
        alerts_generated=result.alerts_generated,
        date=result.date,
    )
