"""신호 변화 이력 테스트."""
from __future__ import annotations

from datetime import datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import app.database as database
from app.models.signal_change import SignalChange
from tools.digest import history
from tools.digest.collector import Digest, Row
from tools.digest.store import Change


def _row(ticker: str, signal: str, *, buy=70, risk=30, price=60_000.0) -> Row:
    return Row(
        ticker=ticker, name=f"{ticker}이름", sources=["watchlist"],
        current_price=price, change_rate=1.0, signal=signal,
        buy_score=buy, sell_score=10, risk_score=risk, risk_level="보통",
        final_buy_score=buy, market_regime="SIDEWAYS", ml_up_probability=0.5,
        reasons=[],
    )


def _digest(rows, at=datetime(2026, 8, 25, 8, 30)) -> Digest:
    return Digest(generated_at=at, period="1y", rows=rows, failures=[])


@pytest.fixture
def session(tmp_path):
    engine = create_engine(
        f"sqlite:///{tmp_path / 'history.db'}", connect_args={"check_same_thread": False}
    )
    database.Base.metadata.create_all(bind=engine)
    db = sessionmaker(bind=engine)()
    yield db
    db.close()


def test_record_stores_the_change_with_the_row_context(session):
    digest = _digest([_row("005930", "BUY", buy=82, risk=41, price=71_000.0)])
    changes = [Change("005930", "삼성전자", "HOLD", "BUY", "up")]

    assert history.record(session, digest, changes) == 1

    stored = session.query(SignalChange).one()
    assert (stored.previous_signal, stored.current_signal, stored.direction) == ("HOLD", "BUY", "up")
    assert (stored.buy_score, stored.risk_score, stored.price) == (82, 41, 71_000.0)
    assert stored.source == "digest"


def test_record_is_idempotent_within_a_day(session):
    digest = _digest([_row("005930", "BUY")])
    changes = [Change("005930", "삼성전자", "HOLD", "BUY", "up")]

    assert history.record(session, digest, changes) == 1
    # 같은 날 두 번 돌려도 이력이 부풀지 않는다.
    assert history.record(session, digest, changes) == 0
    assert session.query(SignalChange).count() == 1


def test_the_same_flip_on_another_day_is_recorded_again(session):
    changes = [Change("005930", "삼성전자", "HOLD", "BUY", "up")]

    history.record(session, _digest([_row("005930", "BUY")], datetime(2026, 8, 25, 8, 30)), changes)
    history.record(session, _digest([_row("005930", "BUY")], datetime(2026, 8, 26, 8, 30)), changes)

    assert session.query(SignalChange).count() == 2


def test_record_handles_a_change_without_a_matching_row(session):
    # 신호가 바뀐 종목이 이번 실행에서 실패해 rows 에 없을 수 있다.
    digest = _digest([])
    changes = [Change("005930", "삼성전자", "HOLD", "BUY", "up")]

    assert history.record(session, digest, changes) == 1
    stored = session.query(SignalChange).one()
    assert stored.price is None and stored.buy_score is None


def test_record_does_nothing_without_changes(session):
    assert history.record(session, _digest([_row("005930", "HOLD")]), []) == 0
    assert session.query(SignalChange).count() == 0


def test_recent_filters_by_window_and_ticker(session):
    now = datetime.utcnow()
    session.add_all([
        SignalChange(ticker="005930", current_signal="BUY", direction="up",
                     source="digest", recorded_at=now - timedelta(days=2)),
        SignalChange(ticker="000660", current_signal="SELL", direction="down",
                     source="digest", recorded_at=now - timedelta(days=2)),
        SignalChange(ticker="005930", current_signal="HOLD", direction="down",
                     source="digest", recorded_at=now - timedelta(days=60)),
    ])
    session.commit()

    assert len(history.recent(session, days=30)) == 2
    assert len(history.recent(session, days=30, ticker="005930")) == 1
    assert len(history.recent(session, days=90, ticker="005930")) == 2


def test_flip_counts_ranks_the_noisiest_tickers_first(session):
    now = datetime.utcnow()
    session.add_all([
        SignalChange(ticker="005930", current_signal="BUY", direction="up",
                     source="digest", recorded_at=now - timedelta(days=1)),
        SignalChange(ticker="005930", current_signal="HOLD", direction="down",
                     source="digest", recorded_at=now - timedelta(days=2)),
        SignalChange(ticker="000660", current_signal="BUY", direction="up",
                     source="digest", recorded_at=now - timedelta(days=1)),
    ])
    session.commit()

    assert history.flip_counts(session, days=30) == {"005930": 2, "000660": 1}
