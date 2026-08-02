from pydantic import BaseModel, Field

from app.schemas.stock import DataSourceMetadata


class ModelPrediction(BaseModel):
    model: str
    predicted_price: float
    test_score: float


class HorizonPrediction(BaseModel):
    horizon_days: int
    predicted_price: float
    expected_return_pct: float
    model_predictions: list[ModelPrediction]
    confidence_score: int = Field(ge=0, le=100)

    model_config = {"protected_namespaces": ()}


class OptimalExit(BaseModel):
    """최적 매도 시점 추천."""

    horizon_days: int
    horizon_label: str            # "약 3일", "약 한 달", "약 3개월"
    target_price: float
    expected_return_pct: float
    confidence_score: int = Field(ge=0, le=100)
    risk_adjusted_score: float    # 위험 조정 종합 점수
    rationale: str                # 추천 근거 (자연어)


class PriceTarget(BaseModel):
    """장기 도달 가능 가격 (보수/중립/낙관)."""

    horizon_days: int            # 기준 horizon (보통 60-120)
    conservative_price: float    # 보수적 시나리오
    base_price: float            # 중립 시나리오
    optimistic_price: float      # 낙관 시나리오
    current_price: float
    expected_return_pct: float   # base 기준
    confidence_score: int = Field(ge=0, le=100)
    rationale: str


class PredictionResponse(DataSourceMetadata):
    ticker: str
    period: str
    current_price: float
    predictions: list[HorizonPrediction]                  # 단기 (1/3/5/20)
    long_term_predictions: list[HorizonPrediction] = []   # 장기 (60/120)
    optimal_exit: OptimalExit | None = None
    price_target: PriceTarget | None = None
    feature_columns: list[str]
    note: str
