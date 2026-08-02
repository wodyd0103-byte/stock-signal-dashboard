from datetime import datetime

from pydantic import BaseModel, Field


class WatchlistCreate(BaseModel):
    ticker: str = Field(min_length=1, max_length=32)
    name: str | None = Field(default=None, max_length=120)


class WatchlistItemResponse(BaseModel):
    id: int
    ticker: str
    name: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class WatchlistSummary(BaseModel):
    id: int
    ticker: str
    name: str | None
    current_price: float | None
    change_rate: float | None
    signal: str | None
    buy_score: int | None
    sell_score: int | None
    risk_score: int | None
    last_analyzed_at: datetime | None
    error: str | None = None
