from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field


Period = Literal["1mo", "3mo", "6mo", "1y", "3y"]


class PricePoint(BaseModel):
    date: date
    open: float
    high: float
    low: float
    close: float
    volume: int
    ma5: float | None = None
    ma20: float | None = None
    ma60: float | None = None
    ma120: float | None = None
    rsi: float | None = None
    macd: float | None = None
    macd_signal: float | None = None
    bollinger_upper: float | None = None
    bollinger_lower: float | None = None


class DataSourceMetadata(BaseModel):
    market: str = "UNKNOWN"
    source: str = "unknown"
    is_sample: bool = False
    provider_status: str = "unknown"
    provider_message: str = ""
    provider_error: str | None = None


class PriceResponse(DataSourceMetadata):
    ticker: str
    period: str
    current_price: float
    previous_close: float
    change: float
    change_rate: float
    volume: int
    currency: str = "KRW/USD"
    last_updated: datetime
    data: list[PricePoint]
    prices: list[PricePoint]


class HealthResponse(BaseModel):
    status: str = "ok"
    service: str = "quant-insight-api"
