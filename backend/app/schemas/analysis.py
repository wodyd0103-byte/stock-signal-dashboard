from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.prediction import HorizonPrediction, OptimalExit, PriceTarget
from app.schemas.stock import DataSourceMetadata, PricePoint


Signal = Literal["STRONG BUY", "BUY", "WEAK BUY", "HOLD", "WEAK SELL", "SELL", "STRONG SELL"]
RiskLevel = Literal["낮음", "보통", "높음", "매우 높음"]
ScoreInfluence = Literal["매수", "매도", "중립"]


class IndicatorDetail(BaseModel):
    name: str
    value: float | str | None
    interpretation: str
    influence: ScoreInfluence
    contribution: int = Field(ge=-100, le=100)


class SupportResistance(BaseModel):
    support: list[float]
    resistance: list[float]
    recent_high: float
    recent_low: float


class SignalScore(BaseModel):
    signal: Signal
    buy_score: int = Field(ge=0, le=100)
    sell_score: int = Field(ge=0, le=100)
    risk_score: int = Field(ge=0, le=100)
    raw_buy_score: int = Field(default=0, ge=0, le=100)
    raw_sell_score: int = Field(default=0, ge=0, le=100)
    buy_score_percentile: float | None = None
    sell_score_percentile: float | None = None
    relative_strength_score: float | None = None
    relative_strength_rank: float | None = None
    liquidity_score: float | None = None
    liquidity_rank: float | None = None
    risk_rank: float | None = None
    regime_score: float | None = None
    ml_up_probability: float | None = None
    ml_signal: str | None = None
    model_confidence: float | None = None
    final_buy_score: int = Field(default=0, ge=0, le=100)
    final_sell_score: int = Field(default=0, ge=0, le=100)
    market_regime: str | None = None
    signal_source: str = "absolute_score"
    score_adjustments: list[str] = []
    hold_reasons: list[str] = []
    buy_score_zone: str
    sell_score_zone: str
    risk_score_zone: str
    score_zone: str
    signal_description: str
    reasons: list[str]
    buy_factors: list[str]
    sell_factors: list[str]

    model_config = {"protected_namespaces": ()}


class SignalResponse(SignalScore, DataSourceMetadata):
    ticker: str
    period: str


class RiskMetric(BaseModel):
    name: str
    value: float | str | bool
    interpretation: str
    contribution: int = Field(ge=0, le=100)


class RiskResponse(BaseModel):
    ticker: str
    period: str
    risk_score: int = Field(ge=0, le=100)
    risk_level: RiskLevel
    metrics: list[RiskMetric]
    reasons: list[str]


class IndicatorResponse(DataSourceMetadata):
    ticker: str
    period: str
    indicators: list[IndicatorDetail]
    levels: SupportResistance
    last_updated: datetime


class AnalysisResponse(DataSourceMetadata):
    ticker: str
    period: str
    current_price: float
    previous_close: float
    change: float
    change_rate: float
    volume: int
    signal: SignalScore
    indicators: list[IndicatorDetail]
    risk: RiskResponse
    predictions: list[HorizonPrediction]
    long_term_predictions: list[HorizonPrediction] = []
    optimal_exit: OptimalExit | None = None
    price_target: PriceTarget | None = None
    market_sentiment: dict | None = None
    supply_demand: dict | None = None
    news_sentiment: dict | None = None
    sector: dict | None = None
    disclosure: dict | None = None
    learned_signal: dict | None = None
    fundamental: dict | None = None
    price_history: list[PricePoint]
    levels: SupportResistance
    disclaimer: str
    last_updated: datetime
