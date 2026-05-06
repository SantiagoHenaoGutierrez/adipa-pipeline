from datetime import datetime, timezone

import requests
from prefect import flow, task

from shared.config import load_config
from shared.db import get_cursor
from shared.logger import get_logger
from shared.models import ExchangeRateApiResponse

logger = get_logger(__name__)

# open.er-api.com: free, no API key, supports CLP/MXN/COP/ARS (ECB doesn't cover them)
EXCHANGE_RATE_URL = "https://open.er-api.com/v6/latest/USD"
TARGET_CURRENCIES = ["CLP", "MXN", "COP", "ARS"]
MAX_RETRIES = 3


def _truncate_to_15min(dt: datetime) -> datetime:
    return dt.replace(minute=(dt.minute // 15) * 15, second=0, microsecond=0)


@task(
    name="fetch-rates-from-api",
    retries=MAX_RETRIES,
    retry_delay_seconds=[1, 2, 4],
)
def fetch_rates_from_api() -> ExchangeRateApiResponse:
    logger.info("fetching_exchange_rates", url=EXCHANGE_RATE_URL)

    response = requests.get(EXCHANGE_RATE_URL, timeout=10)
    response.raise_for_status()

    data = response.json()
    if data.get("result") != "success":
        raise ValueError(f"API returned non-success result: {data.get('result')}")

    all_rates: dict[str, float] = data["rates"]
    filtered_rates = {c: all_rates[c] for c in TARGET_CURRENCIES if c in all_rates}

    missing = set(TARGET_CURRENCIES) - set(filtered_rates)
    if missing:
        logger.warning("currencies_missing_from_api", missing=list(missing))

    result = ExchangeRateApiResponse(
        base=data["base_code"],
        rates=filtered_rates,
        date=datetime.now(timezone.utc).date().isoformat(),
    )

    logger.info(
        "exchange_rates_fetched",
        base=result.base,
        currencies=list(result.rates.keys()),
        api_date=result.date,
    )
    return result


@task(name="upsert-exchange-rates")
def upsert_exchange_rates(api_response: ExchangeRateApiResponse) -> dict[str, int]:
    now = datetime.now(timezone.utc)
    window_start = _truncate_to_15min(now)
    config = load_config()

    inserted = 0
    skipped = 0

    with get_cursor(config) as cursor:
        for currency_to, rate in api_response.rates.items():
            cursor.execute(
                """
                INSERT INTO exchange_rates
                    (currency_from, currency_to, rate, fetched_at, window_start)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (currency_from, currency_to, window_start)
                DO NOTHING
                """,
                (api_response.base, currency_to, rate, now, window_start),
            )
            if cursor.rowcount == 1:
                inserted += 1
            else:
                skipped += 1

    logger.info(
        "exchange_rates_upserted",
        window_start=window_start.isoformat(),
        inserted=inserted,
        skipped=skipped,
    )
    return {"inserted": inserted, "skipped": skipped}


@flow(name="light-pipeline", log_prints=False)
def fetch_exchange_rates() -> None:
    logger.info("light_pipeline_started")

    api_response = fetch_rates_from_api()
    result = upsert_exchange_rates(api_response)

    logger.info(
        "light_pipeline_completed",
        inserted=result["inserted"],
        skipped=result["skipped"],
    )
