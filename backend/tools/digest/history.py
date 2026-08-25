"""digest 자료구조를 신호 이력 서비스에 넘기는 어댑터.

적재·조회 로직은 `app/services/signal_history_service.py`에 있다. 리서치 화면도 같은
데이터를 읽기 때문이다. 여기서는 `Digest`/`Change`를 서비스가 아는 dict로 바꾸기만 한다.
앱이 `tools/`를 import하면 의존 방향이 뒤집히므로 변환은 이쪽 책임이다.

T04에서 digest는 DB를 읽기만 한다고 정했다. 그 규칙의 목적인 추천 이력(회고 데이터)
오염 방지는 그대로다 — digest는 `recommendations`를 건드리지 않는다. `signal_changes`는
digest가 스스로 만드는 자기 기록이라 성격이 다르다.
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.services.signal_history_service import (
    DEFAULT_WINDOW_DAYS,
    flip_counts,
    recent,
    record_changes,
)
from tools.digest.collector import Digest
from tools.digest.store import Change

__all__ = ["DEFAULT_WINDOW_DAYS", "flip_counts", "recent", "record"]


def record(db: Session, digest: Digest, changes: list[Change]) -> int:
    """변화를 적재하고 새로 넣은 건수를 돌려준다."""
    if not changes:
        return 0

    rows = {row.ticker: row for row in digest.rows}
    entries = []
    for change in changes:
        # 신호가 바뀐 종목이 이번 실행에서 실패해 rows 에 없을 수 있다.
        row = rows.get(change.ticker)
        entries.append(
            {
                "ticker": change.ticker,
                "name": change.name,
                "previous_signal": change.previous,
                "current_signal": change.current,
                "direction": change.direction,
                "buy_score": row.final_buy_score if row else None,
                "risk_score": row.risk_score if row else None,
                "price": row.current_price if row else None,
            }
        )

    return record_changes(db, entries, digest.generated_at)
