import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


def _require(key: str) -> str:
    value = os.getenv(key)
    if not value:
        raise RuntimeError(f"Required environment variable '{key}' is not set")
    return value


@dataclass(frozen=True)
class Config:
    postgres_user: str
    postgres_password: str
    postgres_db: str
    postgres_host: str
    postgres_port: int
    alert_threshold_pct: float
    log_level: str
    environment: str

    @property
    def postgres_dsn(self) -> str:
        return (
            f"postgresql://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )


def load_config() -> Config:
    return Config(
        postgres_user=_require("POSTGRES_USER"),
        postgres_password=_require("POSTGRES_PASSWORD"),
        postgres_db=_require("POSTGRES_DB"),
        postgres_host=_require("POSTGRES_HOST"),
        postgres_port=int(os.getenv("POSTGRES_PORT", "5432")),
        alert_threshold_pct=float(os.getenv("ALERT_THRESHOLD_PCT", "5.0")),
        log_level=os.getenv("LOG_LEVEL", "INFO"),
        environment=os.getenv("ENVIRONMENT", "development"),
    )
