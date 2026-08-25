"""신호 변화 이력 — digest가 실행마다 남기는 기록.

JSON 스냅샷은 "직전 대비 무엇이 바뀌었나"만 답한다. 이 테이블은 "이 종목이 지난달
몇 번 뒤집혔나"에 답한다. 스냅샷을 지워도 이력은 남는다.
"""
from datetime import datetime

from sqlalchemy import DateTime, Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class SignalChange(Base):
    __tablename__ = "signal_changes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    ticker: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    # 이번 실행에서 처음 본 종목이면 previous_signal 이 비어 있고 direction 이 "new" 다.
    previous_signal: Mapped[str | None] = mapped_column(String(16), nullable=True)
    current_signal: Mapped[str] = mapped_column(String(16), nullable=False)
    direction: Mapped[str] = mapped_column(String(8), nullable=False)  # up | down | new
    buy_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    risk_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    price: Mapped[float | None] = mapped_column(Float, nullable=True)
    source: Mapped[str] = mapped_column(String(16), nullable=False, default="digest")
    recorded_at: Mapped[datetime] = mapped_column(DateTime, index=True, default=datetime.utcnow)
