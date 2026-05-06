from datetime import date

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, field_validator

from app.services.alert_generator import generate_alerts, upsert_alerts
from app.services.price_calculator import (
    calculate_prices,
    fetch_active_courses,
    fetch_daily_avg_rates,
    fetch_previous_prices,
    upsert_course_prices,
)
from app.shared.config import load_config
from app.shared.logger import get_logger
from app.shared.models import ProcessingResult

router = APIRouter()
logger = get_logger(__name__)


class ProcessRequest(BaseModel):
    date: str

    @field_validator("date")
    @classmethod
    def validate_date(cls, v: str) -> str:
        try:
            date.fromisoformat(v)
        except ValueError as exc:
            raise ValueError(f"Invalid date format '{v}'. Expected YYYY-MM-DD.") from exc
        return v


class ProcessResponse(BaseModel):
    courses_processed: int
    alerts_generated: int
    date: str


@router.post("/process", response_model=ProcessResponse)
def process(request: ProcessRequest) -> ProcessResponse:
    config = load_config()
    target_date = date.fromisoformat(request.date)

    logger.info("process_request_received", date=request.date)

    try:
        courses = fetch_active_courses(config)
        if not courses:
            raise HTTPException(status_code=422, detail="No active courses found")

        avg_rates = fetch_daily_avg_rates(config, target_date)
        previous_prices = fetch_previous_prices(config, target_date)

        price_records = calculate_prices(courses, avg_rates, previous_prices, target_date)
        upsert_course_prices(config, price_records)

        alerts = generate_alerts(config, price_records, config.alert_threshold_pct)
        alerts_count = upsert_alerts(config, alerts)

        result = ProcessingResult(
            courses_processed=len(price_records),
            alerts_generated=alerts_count,
            date=request.date,
        )

        logger.info(
            "process_completed",
            date=request.date,
            courses_processed=result.courses_processed,
            alerts_generated=result.alerts_generated,
        )

        return ProcessResponse(
            courses_processed=result.courses_processed,
            alerts_generated=result.alerts_generated,
            date=result.date,
        )

    except ValueError as exc:
        logger.error("process_value_error", date=request.date, error=str(exc))
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        logger.error("process_unexpected_error", date=request.date, error=str(exc), exc_info=True)
        raise HTTPException(status_code=500, detail="Internal processing error") from exc


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
