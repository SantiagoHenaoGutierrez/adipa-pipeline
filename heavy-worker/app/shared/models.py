from dataclasses import dataclass
from datetime import date
from typing import Optional


@dataclass
class Course:
    id: int
    title: str
    slug: str
    base_price_usd: float
    active: bool


@dataclass
class ExchangeRateSummary:
    currency_from: str
    currency_to: str
    avg_rate: float
    sample_count: int


@dataclass
class CoursePriceRecord:
    course_id: int
    country: str
    currency: str
    price_local: float
    exchange_rate_used: float
    calculated_date: date
    variation_pct: Optional[float]


@dataclass
class PriceAlertRecord:
    course_id: int
    country: str
    previous_price: Optional[float]
    current_price: float
    variation_pct: float
    alert_date: date


@dataclass
class ProcessingResult:
    courses_processed: int
    alerts_generated: int
    date: str
