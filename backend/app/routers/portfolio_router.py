"""포트폴리오 라우터 — 보유 CRUD + 분석."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.holding import Holding
from app.routers.stock_router import (
    _build_signal,
    data_provider,
    indicator_service,
    risk_service,
)
from app.schemas.portfolio import HoldingCreate, HoldingResponse
from app.services.portfolio_service import PortfolioService

router = APIRouter(prefix="/portfolio", tags=["portfolio"])

_service = PortfolioService(
    data_provider=data_provider,
    indicator_service=indicator_service,
    risk_service=risk_service,
    build_signal_fn=_build_signal,  # 경량 신호 (sentiment/news 인자 미전달 → 기술+ML+regime)
)


@router.get("/holdings", response_model=list[HoldingResponse])
def list_holdings(db: Session = Depends(get_db)) -> list[Holding]:
    return db.query(Holding).order_by(Holding.created_at.desc()).all()


@router.post("/holdings", response_model=HoldingResponse, status_code=status.HTTP_201_CREATED)
def add_holding(payload: HoldingCreate, db: Session = Depends(get_db)) -> Holding:
    ticker = data_provider.resolve_ticker(payload.ticker)
    existing = db.query(Holding).filter(Holding.ticker == ticker).first()
    if existing:
        # 평단/수량 갱신 (재매수 평균)
        total_qty = existing.quantity + payload.quantity
        existing.avg_price = (
            (existing.avg_price * existing.quantity + payload.avg_price * payload.quantity) / total_qty
            if total_qty > 0 else payload.avg_price
        )
        existing.quantity = total_qty
        if payload.name:
            existing.name = payload.name
        db.commit()
        db.refresh(existing)
        return existing

    item = Holding(ticker=ticker, name=payload.name, quantity=payload.quantity, avg_price=payload.avg_price)
    db.add(item)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="이미 등록된 종목입니다.")
    db.refresh(item)
    return item


@router.delete("/holdings/{ticker}", status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
def delete_holding(ticker: str, db: Session = Depends(get_db)) -> Response:
    item = db.query(Holding).filter(Holding.ticker == data_provider.resolve_ticker(ticker)).first()
    if not item:
        raise HTTPException(status_code=404, detail="보유 종목을 찾을 수 없습니다.")
    db.delete(item)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


def _holdings_dicts(db: Session) -> list[dict]:
    items = db.query(Holding).order_by(Holding.created_at.desc()).all()
    return [
        {"ticker": h.ticker, "name": h.name, "quantity": h.quantity, "avg_price": h.avg_price}
        for h in items
    ]


@router.get("/analysis")
def analyze_portfolio(db: Session = Depends(get_db)) -> dict[str, Any]:
    """보유 전체 손익/신호/집중도/조언."""
    return _service.analyze(_holdings_dicts(db)).to_dict()


def _parse_weights(raw: str | None) -> dict[str, float] | None:
    """'005930:40,000660:60' → {ticker: 비중(0~1)}. 형식 오류 항목은 무시."""
    if not raw or not raw.strip():
        return None
    out: dict[str, float] = {}
    for pair in raw.split(","):
        if ":" not in pair:
            continue
        t, _, v = pair.partition(":")
        t = data_provider.resolve_ticker(t.strip())
        try:
            pct = float(v.strip())
        except ValueError:
            continue
        if pct > 0:
            out[t] = pct / 100.0
    return out or None


@router.get("/rebalance")
def rebalance_portfolio(
    cash: float = Query(0.0, ge=0),
    strategy: str = Query("signal", pattern="^(equal|signal|risk_parity)$"),
    max_weight: float = Query(35.0, ge=10, le=100),
    cash_buffer: float = Query(0.0, ge=0, le=90),
    weights: str | None = Query(None, description="수동 목표비중 'ticker:pct,...' (지정 시 strategy 무시)"),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """목표 비중 → 종목별 매수/매도 수량(정수) + 거래비용 + 현금버퍼."""
    return _service.rebalance(
        _holdings_dicts(db), cash=cash, strategy=strategy,
        max_weight=max_weight / 100, cash_buffer_pct=cash_buffer / 100,
        custom_weights=_parse_weights(weights),
    )


@router.get("/optimize")
def optimize_portfolio(
    method: str = Query("max_sharpe", pattern="^(max_sharpe|min_variance)$"),
    max_weight: float = Query(40.0, ge=10, le=100),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Markowitz 최적 비중 (최대샤프/최소분산)."""
    from app.services.optimizer_service import OptimizerService
    tickers = [h.ticker for h in db.query(Holding).all()]
    res = OptimizerService(data_provider).optimize(tickers, method=method, max_weight=max_weight / 100)
    if res is None:
        return {"error": "최적화에 종목 2개 이상 + 충분한 가격 이력이 필요합니다."}
    return res.to_dict()
