from datetime import date
from typing import Optional

import pandas as pd

from app.shared.config import Config
from app.shared.db import get_connection
from app.shared.logger import get_logger
from app.shared.models import (
    Course,
    CoursePriceRecord,
    ExchangeRateSummary,
)

logger = get_logger(__name__)

COUNTRY_CURRENCY_MAP: dict[str, str] = {
    "CL": "CLP",
    "MX": "MXN",
    "CO": "COP",
    "AR": "ARS",
}


def fetch_active_courses(config: Config) -> list[Course]:
    with get_connection(config) as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT id, title, slug, base_price_usd, active FROM courses WHERE active = TRUE"
            )
            rows = cursor.fetchall()

    courses = [
        Course(id=r[0], title=r[1], slug=r[2], base_price_usd=float(r[3]), active=r[4])
        for r in rows
    ]
    logger.info("active_courses_fetched", count=len(courses))
    return courses


def fetch_daily_avg_rates(
    config: Config, target_date: date
) -> dict[str, ExchangeRateSummary]:
    with get_connection(config) as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT currency_from, currency_to, AVG(rate) as avg_rate, COUNT(*) as samples
                FROM exchange_rates
                WHERE DATE(window_start AT TIME ZONE 'UTC') = %s
                  AND currency_from = 'USD'
                GROUP BY currency_from, currency_to
                """,
                (target_date,),
            )
            rows = cursor.fetchall()

    if not rows:
        raise ValueError(
            f"No exchange rate data found for date {target_date}. "
            "Ensure the light pipeline has run before triggering the heavy pipeline."
        )

    summaries = {
        r[1]: ExchangeRateSummary(
            currency_from=r[0],
            currency_to=r[1],
            avg_rate=float(r[2]),
            sample_count=int(r[3]),
        )
        for r in rows
    }
    logger.info(
        "daily_avg_rates_fetched",
        date=target_date.isoformat(),
        currencies=list(summaries.keys()),
    )
    return summaries


def fetch_previous_prices(
    config: Config, target_date: date
) -> dict[tuple[int, str], float]:
    with get_connection(config) as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT course_id, country, price_local
                FROM course_prices
                WHERE calculated_date = (
                    SELECT MAX(calculated_date)
                    FROM course_prices
                    WHERE calculated_date < %s
                )
                """,
                (target_date,),
            )
            rows = cursor.fetchall()

    return {(r[0], r[1]): float(r[2]) for r in rows}


def calculate_prices(
    courses: list[Course],
    avg_rates: dict[str, ExchangeRateSummary],
    previous_prices: dict[tuple[int, str], float],
    target_date: date,
) -> list[CoursePriceRecord]:
    records: list[CoursePriceRecord] = []

    courses_df = pd.DataFrame(
        [{"id": c.id, "base_price_usd": c.base_price_usd} for c in courses]
    )

    for country, currency in COUNTRY_CURRENCY_MAP.items():
        if currency not in avg_rates:
            logger.warning(
                "missing_exchange_rate", currency=currency, country=country
            )
            continue

        rate_summary = avg_rates[currency]
        avg_rate = rate_summary.avg_rate

        country_df = courses_df.copy()
        country_df["price_local"] = (country_df["base_price_usd"] * avg_rate).round(2)
        country_df["country"] = country
        country_df["currency"] = currency
        country_df["avg_rate"] = avg_rate

        for _, row in country_df.iterrows():
            course_id = int(row["id"])
            price_local = float(row["price_local"])
            prev_price = previous_prices.get((course_id, country))

            variation_pct: Optional[float] = None
            if prev_price is not None and prev_price > 0:
                variation_pct = round(
                    ((price_local - prev_price) / prev_price) * 100, 2
                )

            records.append(
                CoursePriceRecord(
                    course_id=course_id,
                    country=country,
                    currency=currency,
                    price_local=price_local,
                    exchange_rate_used=avg_rate,
                    calculated_date=target_date,
                    variation_pct=variation_pct,
                )
            )

    logger.info("prices_calculated", count=len(records), date=target_date.isoformat())
    return records


def upsert_course_prices(
    config: Config, records: list[CoursePriceRecord]
) -> int:
    upserted = 0
    with get_connection(config) as conn:
        with conn.cursor() as cursor:
            for record in records:
                cursor.execute(
                    """
                    INSERT INTO course_prices
                        (course_id, country, currency, price_local,
                         exchange_rate_used, calculated_date, variation_pct)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (course_id, country, calculated_date)
                    DO UPDATE SET
                        currency           = EXCLUDED.currency,
                        price_local        = EXCLUDED.price_local,
                        exchange_rate_used = EXCLUDED.exchange_rate_used,
                        variation_pct      = EXCLUDED.variation_pct
                    """,
                    (
                        record.course_id,
                        record.country,
                        record.currency,
                        record.price_local,
                        record.exchange_rate_used,
                        record.calculated_date,
                        record.variation_pct,
                    ),
                )
                upserted += 1

    logger.info("course_prices_upserted", count=upserted)
    return upserted
