"""관심종목·보유 종목 등록 로직.

서버를 띄우지 않고 앱과 같은 SQLite에 직접 쓴다. 동작은 REST 엔드포인트와 맞춘다 —
관심종목 추가는 멱등이고, 보유 추가는 재매수 평균으로 합친다. 두 경로가 다르게 굴면
CLI로 넣은 종목과 화면으로 넣은 종목이 서로 다른 상태가 된다.
"""
from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.core.stock_universe import KOREAN_REPRESENTATIVE_STOCKS, US_REPRESENTATIVE_STOCKS
from app.models.holding import Holding
from app.models.watchlist import WatchlistItem
from app.services.analysis_service import data_provider


@dataclass
class Resolved:
    ticker: str
    name: str | None


def _universe() -> list[dict]:
    return [*KOREAN_REPRESENTATIVE_STOCKS, *US_REPRESENTATIVE_STOCKS]


def resolve(query: str) -> Resolved:
    """티커든 종목명이든 받는다. 대표 종목 목록에 있으면 이름까지 채워준다.

    목록에 없는 종목도 그대로 통과시킨다 — 대표 목록은 편의용이지 허용 목록이 아니다.
    """
    text = query.strip()
    lowered = text.casefold()

    for item in _universe():
        if item["name"].casefold() == lowered:
            return Resolved(ticker=item["ticker"], name=item["name"])

    ticker = data_provider.resolve_ticker(text)
    for item in _universe():
        if item["ticker"] == ticker:
            return Resolved(ticker=ticker, name=item["name"])
    return Resolved(ticker=ticker, name=None)


def add_watch(db: Session, ticker: str, name: str | None = None) -> tuple[WatchlistItem, bool]:
    """이미 있으면 그대로 둔다. 두 번 실행해도 같은 결과 (created=False)."""
    existing = db.query(WatchlistItem).filter(WatchlistItem.ticker == ticker).first()
    if existing:
        if name and not existing.name:
            existing.name = name
            db.commit()
            db.refresh(existing)
        return existing, False

    item = WatchlistItem(ticker=ticker, name=name)
    db.add(item)
    db.commit()
    db.refresh(item)
    return item, True


def remove_watch(db: Session, ticker: str) -> bool:
    item = db.query(WatchlistItem).filter(WatchlistItem.ticker == ticker).first()
    if not item:
        return False
    db.delete(item)
    db.commit()
    return True


def add_hold(
    db: Session,
    ticker: str,
    quantity: float,
    avg_price: float,
    name: str | None = None,
    replace: bool = False,
) -> tuple[Holding, bool]:
    """기본은 재매수 평균으로 합친다. `replace=True`면 수량·평단을 통째로 덮어쓴다."""
    existing = db.query(Holding).filter(Holding.ticker == ticker).first()
    if existing:
        if replace:
            existing.quantity = quantity
            existing.avg_price = avg_price
        else:
            total = existing.quantity + quantity
            existing.avg_price = (
                (existing.avg_price * existing.quantity + avg_price * quantity) / total
                if total > 0
                else avg_price
            )
            existing.quantity = total
        if name:
            existing.name = name
        db.commit()
        db.refresh(existing)
        return existing, False

    item = Holding(ticker=ticker, name=name, quantity=quantity, avg_price=avg_price)
    db.add(item)
    db.commit()
    db.refresh(item)
    return item, True


def remove_hold(db: Session, ticker: str) -> bool:
    item = db.query(Holding).filter(Holding.ticker == ticker).first()
    if not item:
        return False
    db.delete(item)
    db.commit()
    return True


def list_watch(db: Session) -> list[WatchlistItem]:
    return db.query(WatchlistItem).order_by(WatchlistItem.created_at.desc()).all()


def list_hold(db: Session) -> list[Holding]:
    return db.query(Holding).order_by(Holding.created_at.desc()).all()
