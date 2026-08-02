"""
급등주 포착 (Triple Barrier 라벨링 + 분류 모델) 스키마.
"""
from __future__ import annotations

from pydantic import BaseModel, Field

from app.schemas.stock import DataSourceMetadata


class SurgeItem(DataSourceMetadata):
    rank: int
    ticker: str
    name: str
    market: str
    current_price: float
    change_rate: float
    surge_probability: float = Field(ge=0, le=1)  # 모델 예측 확률
    base_rate: float = Field(ge=0, le=1)          # 과거 급등 비율 (기저)
    lift: float                                    # surge_probability / base_rate
    expected_target_pct: float                     # 라벨 upper bound (%)
    horizon_days: int                              # 라벨 시간창
    signal_label: str                              # 자연어 ("매우 강함", "강함" 등)
    train_samples: int
    train_positive: int
    cv_score: float                                # walk-forward AUC
    reasons: list[str] = []


class SurgeScanResponse(BaseModel):
    updated_at: str
    horizon_days: int
    upper_pct: float
    lower_pct: float
    market: str
    items: list[SurgeItem]
    failed: list[dict] = []
    total_scanned: int
    total_strong: int                              # 확률 ≥ 0.6
    disclaimer: str
