from fastapi import FastAPI

from app.routes.process import router
from app.shared.config import load_config
from app.shared.logger import get_logger

logger = get_logger(__name__)

config = load_config()

app = FastAPI(
    title="ADIPA Heavy Worker",
    description="Processes localized course prices and generates variation alerts",
    version="1.0.0",
)

app.include_router(router)


@app.on_event("startup")
def on_startup() -> None:
    logger.info(
        "heavy_worker_started",
        environment=config.environment,
        log_level=config.log_level,
        alert_threshold_pct=config.alert_threshold_pct,
    )
