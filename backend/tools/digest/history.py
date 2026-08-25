"""신호 변화를 DB에 기록하고 되읽는다.

T04에서 digest는 DB를 읽기만 한다고 정했다. 그 규칙의 목적은 **추천 이력(회고 데이터)을
오염시키지 않는 것**이었고, 지금도 그대로다 — digest는 `recommendations`를 건드리지 않는다.
`signal_changes`는 digest가 스스로 만든 자기 기록이라 성격이 다르다.

같은 날 여러 번 돌려도 같은 변화가 중복 적재되지 않는다.
"""
from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.models.signal_change import SignalChange
from tools.digest.collector import Digest
from tools.digest.store import Change


def record(db: Session, digest: Digest, changes: list[Change]) -> int:
    """변화를 적재하고 새로 넣은 건수를 돌려준다."""
    if not changes:
        return 0

    prices = {row.ticker: row for row in digest.rows}
    recorded_at = digest.generated_at
    day_start = datetime(recorded_at.year, recorded_at.month, recorded_at.day)

    inserted = 0
    for change in changes:
        # 같은 날 같은 종목의 같은 전환은 한 번만. 하루에 두 번 돌려도 이력이 부풀지 않는다.
        duplicate = (
            db.query(SignalChange)
            .filter(
                SignalChange.ticker == change.ticker,
                SignalChange.current_signal == change.current,
                SignalChange.recorded_at >= day_start,
            )
            .first()
        )
        if duplicate:
            continue

        row = prices.get(change.ticker)
        db.add(
            SignalChange(
                ticker=change.ticker,
                name=change.name,
                previous_signal=change.previous,
                current_signal=change.current,
                direction=change.direction,
                buy_score=row.final_buy_score if row else None,
                risk_score=row.risk_score if row else None,
                price=row.current_price if row else None,
                source="digest",
                recorded_at=recorded_at,
            )
        )
        inserted += 1

    db.commit()
    return inserted


def recent(db: Session, days: int = 30, ticker: str | None = None) -> list[SignalChange]:
    """최근 N일 이력. 리서치 탭이나 회고 분석이 읽을 자리."""
    since = datetime.utcnow() - timedelta(days=days)
    query = db.query(SignalChange).filter(SignalChange.recorded_at >= since)
    if ticker:
        query = query.filter(SignalChange.ticker == ticker)
    return query.order_by(SignalChange.recorded_at.desc()).all()


def flip_counts(db: Session, days: int = 30) -> dict[str, int]:
    """종목별 전환 횟수. 자주 뒤집히는 종목일수록 신호를 덜 믿어야 한다."""
    counts: dict[str, int] = {}
    for row in recent(db, days):
        counts[row.ticker] = counts.get(row.ticker, 0) + 1
    return dict(sorted(counts.items(), key=lambda item: (-item[1], item[0])))
