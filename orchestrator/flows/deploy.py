from datetime import timedelta

from prefect import serve

from heavy_pipeline import run_heavy_pipeline
from light_pipeline import fetch_exchange_rates
from shared.logger import get_logger

logger = get_logger(__name__)


def deploy_flows() -> None:
    logger.info("deploying_flows")

    light_deployment = fetch_exchange_rates.to_deployment(
        name="light-pipeline-every-15min",
        interval=timedelta(minutes=15),
        tags=["light", "exchange-rates"],
        description="Fetches USD exchange rates every 15 minutes",
    )

    heavy_deployment = run_heavy_pipeline.to_deployment(
        name="heavy-pipeline-daily-0600",
        cron="0 6 * * *",
        tags=["heavy", "pricing", "alerts"],
        description="Calculates localized course prices and generates alerts daily at 06:00",
    )

    logger.info("starting_prefect_serve")
    serve(light_deployment, heavy_deployment)


if __name__ == "__main__":
    deploy_flows()
