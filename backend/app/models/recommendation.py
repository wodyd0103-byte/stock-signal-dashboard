"""회고용 추천 기록 모델 — 분석 시점 신호 + N일 후 실제 성과."""
from datetime import datetime

from sqlalchemy import DateTime, Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Recommendation(Base):
    __tablename__ = "recommendations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    ticker: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    market: Mapped[str | None] = mapped_column(String(8), nullable=True)

    # 기록 시점 스냅샷
    signal: Mapped[str] = mapped_column(String(20), nullable=False)
    buy_score: Mapped[int] = mapped_column(Integer, default=0)
    risk_score: Mapped[int] = mapped_column(Integer, default=0)
    price_at_rec: Mapped[float] = mapped_column(Float, nullable=False)
    recommended_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)

    # 평가 결과 (채점 후 채워짐)
    evaluated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    price_after: Mapped[float | None] = mapped_column(Float, nullable=True)
    return_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    horizon_days: Mapped[int] = mapped_column(Integer, default=5)
    hit: Mapped[int | None] = mapped_column(Integer, nullable=True)  # 1=적중(매수신호+수익), 0=실패, None=미평가
    status: Mapped[str] = mapped_column(String(16), default="open", index=True)  # open / evaluated
