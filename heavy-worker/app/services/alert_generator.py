from datetime import date
from typing import Optional

from app.shared.config import Config
from app.shared.db import get_connection
from app.shared.logger import get_logger
from app.shared.models import CoursePriceRecord, PriceAlertRecord

logger = get_logger(__name__)


def _fetch_previous_price(
    cursor,
    course_id: int,
    country: str,
    target_date: date,
) -> Optional[float]:
    cursor.execute(
        """
        SELECT price_local FROM course_prices
        WHERE course_id = %s AND country = %s AND calculated_date < %s
        ORDER BY calculated_date DESC
        LIMIT 1
        """,
        (course_id, country, target_date),
    )
    row = cursor.fetchone()
    return float(row[0]) if row else None


def generate_alerts(
    config: Config,
    price_records: list[CoursePriceRecord],
    threshold_pct: float,
) -> list[PriceAlertRecord]:
    alerts: list[PriceAlertRecord] = []

    for record in price_records:
        if record.variation_pct is None:
            continue
        if abs(record.variation_pct) > threshold_pct:
            previous_price: Optional[float] = None
            if record.variation_pct != 0:
                previous_price = round(
                    record.price_local / (1 + record.variation_pct / 100), 2
                )

            alerts.append(
                PriceAlertRecord(
                    course_id=record.course_id,
                    country=record.country,
                    previous_price=previous_price,
                    current_price=record.price_local,
                    variation_pct=record.variation_pct,
                    alert_date=record.calculated_date,
                )
            )

    logger.info(
        "alerts_generated",
        count=len(alerts),
        threshold_pct=threshold_pct,
    )
    return alerts


def upsert_alerts(config: Config, alerts: list[PriceAlertRecord]) -> int:
    if not alerts:
        return 0

    upserted = 0
    with get_connection(config) as conn:
        with conn.cursor() as cursor:
            for alert in alerts:
                cursor.execute(
                    """
                    INSERT INTO price_alerts
                        (course_id, country, previous_price, current_price,
                         variation_pct, alert_date)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    ON CONFLICT (course_id, country, alert_date)
                    DO UPDATE SET
                        previous_price = EXCLUDED.previous_price,
                        current_price  = EXCLUDED.current_price,
                        variation_pct  = EXCLUDED.variation_pct,
                        resolved       = FALSE
                    """,
                    (
                        alert.course_id,
                        alert.country,
                        alert.previous_price,
                        alert.current_price,
                        alert.variation_pct,
                        alert.alert_date,
                    ),
                )
                upserted += 1

    logger.info("alerts_upserted", count=upserted)
    return upserted
