from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.watchlist import WatchlistItem
from app.services.analysis_service import (
    data_provider,
    load_enriched,
    prediction_service,
    quote_from_frame,
    risk_service,
    signal_service,
)
from app.schemas.watchlist import WatchlistCreate, WatchlistItemResponse, WatchlistSummary


router = APIRouter(prefix="/watchlist", tags=["watchlist"])


@router.get("", response_model=list[WatchlistSummary])
def list_watchlist(db: Session = Depends(get_db)) -> list[WatchlistSummary]:
    items = db.query(WatchlistItem).order_by(WatchlistItem.created_at.desc()).all()
    summaries: list[WatchlistSummary] = []
    for item in items:
        try:
            result, enriched = load_enriched(item.ticker, "1y")
            quote = quote_from_frame(result, "1y", enriched)
            risk = risk_service.analyze(result.ticker, "1y", enriched)
            prediction = prediction_service.predict(result.ticker, "1y", enriched)
            signal = signal_service.score(enriched, risk.risk_score, prediction)
            summaries.append(
                WatchlistSummary(
                    id=item.id,
                    ticker=item.ticker,
                    name=item.name,
                    current_price=quote["current_price"],
                    change_rate=quote["change_rate"],
                    signal=signal.signal,
                    buy_score=signal.buy_score,
                    sell_score=signal.sell_score,
                    risk_score=signal.risk_score,
                    last_analyzed_at=datetime.utcnow(),
                )
            )
        except Exception as exc:
            summaries.append(
                WatchlistSummary(
                    id=item.id,
                    ticker=item.ticker,
                    name=item.name,
                    current_price=None,
                    change_rate=None,
                    signal=None,
                    buy_score=None,
                    sell_score=None,
                    risk_score=None,
                    last_analyzed_at=None,
                    error=str(exc),
                )
            )
    return summaries


@router.post("", response_model=WatchlistItemResponse, status_code=status.HTTP_201_CREATED)
def add_watchlist(payload: WatchlistCreate, db: Session = Depends(get_db)) -> WatchlistItemResponse:
    ticker = data_provider.resolve_ticker(payload.ticker)
    existing = db.query(WatchlistItem).filter(WatchlistItem.ticker == ticker).first()
    if existing:
        return WatchlistItemResponse.model_validate(existing)

    item = WatchlistItem(ticker=ticker, name=payload.name)
    db.add(item)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        existing = db.query(WatchlistItem).filter(WatchlistItem.ticker == ticker).first()
        if existing:
            return WatchlistItemResponse.model_validate(existing)
        raise
    db.refresh(item)
    return WatchlistItemResponse.model_validate(item)


@router.delete("/{ticker}", status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
def delete_watchlist(ticker: str, db: Session = Depends(get_db)) -> Response:
    item = db.query(WatchlistItem).filter(WatchlistItem.ticker == data_provider.resolve_ticker(ticker)).first()
    if not item:
        raise HTTPException(status_code=404, detail="관심종목을 찾을 수 없습니다.")
    db.delete(item)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
