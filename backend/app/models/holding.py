"""보유 종목 모델 — 포트폴리오 설계사용."""
from datetime import datetime

from sqlalchemy import DateTime, Float, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Holding(Base):
    __tablename__ = "holdings"
    __table_args__ = (UniqueConstraint("ticker", name="uq_holding_ticker"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    ticker: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    quantity: Mapped[float] = mapped_column(Float, nullable=False)        # 보유 수량
    avg_price: Mapped[float] = mapped_column(Float, nullable=False)       # 평균 매입가
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
