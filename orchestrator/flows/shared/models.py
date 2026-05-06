from dataclasses import dataclass
from datetime import datetime, date
from typing import Optional


@dataclass
class ExchangeRate:
    currency_from: str
    currency_to: str
    rate: float
    fetched_at: datetime
    window_start: datetime


@dataclass
class Course:
    id: int
    title: str
    slug: str
    base_price_usd: float
    active: bool


@dataclass
class CoursePrice:
    course_id: int
    country: str
    currency: str
    price_local: float
    exchange_rate_used: float
    calculated_date: date
    variation_pct: Optional[float]


@dataclass
class PriceAlert:
    course_id: int
    country: str
    previous_price: Optional[float]
    current_price: float
    variation_pct: float
    alert_date: date


@dataclass
class HeavyPipelineResult:
    courses_processed: int
    alerts_generated: int
    date: str


@dataclass
class ExchangeRateApiResponse:
    base: str
    rates: dict[str, float]
    date: str
