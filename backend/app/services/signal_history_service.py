"""신호 변화 이력.

digest CLI가 실행마다 적재하고, 리서치 화면이 되읽는다. 스냅샷이 "직전 대비 무엇이
바뀌었나"를 답한다면 이 테이블은 "이 종목이 최근 몇 번 뒤집혔나"를 답한다.

CLI 자료구조(`Digest`, `Change`)를 여기서 알지 않는다 — 앱이 `tools/`를 import하면
의존 방향이 뒤집힌다. 적재는 평범한 dict를 받고, 변환은 `tools/digest/history.py`가 한다.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Iterable

from sqlalchemy.orm import Session

from app.models.signal_change import SignalChange

DEFAULT_WINDOW_DAYS = 30

# 한 번은 그 전환 자체일 뿐이라 셀 것이 없다. 두 번부터가 "오락가락한다"는 신호다.
FLIP_NOTE_FLOOR = 2


def record_changes(db: Session, entries: Iterable[dict[str, Any]], recorded_at: datetime) -> int:
    """변화를 적재하고 새로 넣은 건수를 돌려준다.

    같은 날 같은 종목의 같은 전환은 한 번만 남는다. 하루에 두 번 돌린다고 이력이
    부풀면 "몇 번 뒤집혔나"가 실행 횟수를 세는 지표가 된다.
    """
    day_start = datetime(recorded_at.year, recorded_at.month, recorded_at.day)
    inserted = 0

    for entry in entries:
        ticker = entry["ticker"]
        current = entry["current_signal"]
        duplicate = (
            db.query(SignalChange)
            .filter(
                SignalChange.ticker == ticker,
                SignalChange.kind == entry.get("kind", "signal"),
                SignalChange.current_signal == current,
                SignalChange.recorded_at >= day_start,
            )
            .first()
        )
        if duplicate:
            continue

        db.add(
            SignalChange(
                kind=entry.get("kind", "signal"),
                ticker=ticker,
                name=entry.get("name"),
                previous_signal=entry.get("previous_signal"),
                current_signal=current,
                direction=entry.get("direction", "up"),
                buy_score=entry.get("buy_score"),
                risk_score=entry.get("risk_score"),
                price=entry.get("price"),
                source=entry.get("source", "digest"),
                recorded_at=recorded_at,
            )
        )
        inserted += 1

    if inserted:
        db.commit()
    return inserted


def recent(db: Session, days: int = DEFAULT_WINDOW_DAYS, ticker: str | None = None) -> list[SignalChange]:
    since = datetime.utcnow() - timedelta(days=days)
    query = db.query(SignalChange).filter(SignalChange.recorded_at >= since)
    if ticker:
        query = query.filter(SignalChange.ticker == ticker)
    return query.order_by(SignalChange.recorded_at.desc()).all()


def flip_counts(db: Session, days: int = DEFAULT_WINDOW_DAYS) -> dict[str, int]:
    """종목별 등급 전환 횟수. 자주 뒤집히는 종목일수록 신호를 덜 믿어야 한다.

    점수 이동은 세지 않는다. 등급을 넘지 않은 움직임까지 "뒤집혔다"고 세면
    그 숫자가 무엇을 뜻하는지 흐려진다.
    """
    counts: dict[str, int] = {}
    for row in recent(db, days):
        if row.kind != "signal":
            continue
        counts[row.ticker] = counts.get(row.ticker, 0) + 1
    return dict(sorted(counts.items(), key=lambda item: (-item[1], item[0])))


def _as_dict(row: SignalChange) -> dict[str, Any]:
    return {
        "id": row.id,
        "kind": row.kind,
        "ticker": row.ticker,
        "name": row.name,
        "previous_signal": row.previous_signal,
        "current_signal": row.current_signal,
        "direction": row.direction,
        "buy_score": row.buy_score,
        "risk_score": row.risk_score,
        "price": row.price,
        "recorded_at": row.recorded_at.isoformat() if row.recorded_at else None,
    }


def summary(
    db: Session,
    days: int = DEFAULT_WINDOW_DAYS,
    limit: int = 40,
    ticker: str | None = None,
) -> dict[str, Any]:
    """신호 전환 요약 — 자주 뒤집힌 종목과 최근 전환 목록.

    `ticker` 를 주면 그 종목만 본다. 종목 분석 화면이 "이 신호, 원래 자주 뒤집히나"를
    물을 때 쓴다. 그때 `flips` 는 최대 한 줄이다.
    """
    rows = recent(db, days, ticker)

    counts: dict[str, int] = {}
    names: dict[str, str | None] = {}
    for row in rows:
        # rows 는 최신순이므로 처음 만난 이름이 가장 최근 이름이다.
        names.setdefault(row.ticker, row.name)
        if row.kind != "signal":
            continue
        counts[row.ticker] = counts.get(row.ticker, 0) + 1

    flips = [
        {"ticker": ticker, "name": names.get(ticker), "count": count}
        for ticker, count in sorted(counts.items(), key=lambda item: (-item[1], item[0]))
        if count >= FLIP_NOTE_FLOOR
    ]

    return {
        "days": days,
        "ticker": ticker,
        "total": len(rows),
        "tickers": len(counts),
        "flips": flips,
        "recent": [_as_dict(row) for row in rows[:limit]],
    }
