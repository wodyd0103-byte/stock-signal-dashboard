"""회고 라우터 — 추천 적중률, 채점 트리거."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.services import signal_history_service
from app.services.retrospective_service import RetrospectiveService

router = APIRouter(prefix="/retrospective", tags=["retrospective"])
_service = RetrospectiveService()


def _price_fn(ticker: str, due) -> float | None:
    from app.services.analysis_service import close_on
    return close_on(ticker, due)


@router.get("/summary")
def get_summary(db: Session = Depends(get_db)) -> dict[str, Any]:
    """적중률/평균수익/신호별 집계 + 최근 기록."""
    return _service.summary(db)


@router.post("/evaluate")
def evaluate(db: Session = Depends(get_db)) -> dict[str, Any]:
    """horizon 경과 추천 채점 (수동 트리거). 스케줄러도 호출."""
    n = _service.evaluate_due(db, _price_fn)
    return {"evaluated": n, **_service.summary(db)}


@router.get("/signal-changes")
def get_signal_changes(
    days: int = Query(30, ge=1, le=365),
    ticker: str | None = Query(None, description="주면 그 종목만"),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """digest가 남긴 신호 전환 이력 — 자주 뒤집힌 종목과 최근 전환."""
    return signal_history_service.summary(db, days=days, ticker=ticker)
