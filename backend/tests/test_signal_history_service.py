"""신호 이력 서비스 — 리서치 화면이 읽는 요약."""
from __future__ import annotations

from datetime import datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import app.database as database
from app.models.signal_change import SignalChange
from app.services import signal_history_service as service


@pytest.fixture
def session(tmp_path):
    engine = create_engine(
        f"sqlite:///{tmp_path / 'history.db'}", connect_args={"check_same_thread": False}
    )
    database.Base.metadata.create_all(bind=engine)
    db = sessionmaker(bind=engine)()
    yield db
    db.close()


def _change(ticker, current, *, name=None, days_ago=1, direction="up"):
    return SignalChange(
        ticker=ticker,
        name=name,
        current_signal=current,
        direction=direction,
        source="digest",
        recorded_at=datetime.utcnow() - timedelta(days=days_ago),
    )


def test_record_changes_stores_the_entry(session):
    inserted = service.record_changes(
        session,
        [{
            "ticker": "005930", "name": "삼성전자", "previous_signal": "HOLD",
            "current_signal": "BUY", "direction": "up",
            "buy_score": 82, "risk_score": 41, "price": 71_000.0,
        }],
        datetime(2026, 8, 25, 8, 30),
    )

    assert inserted == 1
    row = session.query(SignalChange).one()
    assert (row.previous_signal, row.current_signal, row.price) == ("HOLD", "BUY", 71_000.0)
    assert row.source == "digest"


def test_record_changes_is_idempotent_within_a_day(session):
    entry = {"ticker": "005930", "current_signal": "BUY", "direction": "up"}
    at = datetime(2026, 8, 25, 8, 30)

    assert service.record_changes(session, [entry], at) == 1
    assert service.record_changes(session, [entry], at) == 0
    assert session.query(SignalChange).count() == 1


def test_summary_ranks_the_noisiest_tickers_first(session):
    session.add_all([
        _change("005930", "BUY", name="삼성전자", days_ago=1),
        _change("005930", "HOLD", name="삼성전자", days_ago=3),
        _change("005930", "BUY", name="삼성전자", days_ago=6),
        _change("000660", "SELL", name="SK하이닉스", days_ago=2),
        _change("000660", "HOLD", name="SK하이닉스", days_ago=4),
        _change("035720", "BUY", name="카카오", days_ago=2),
    ])
    session.commit()

    result = service.summary(session, days=30)

    assert result["total"] == 6
    assert result["tickers"] == 3
    # 1회짜리는 셀 것이 없어 flips 에 나오지 않는다.
    assert [(f["ticker"], f["count"]) for f in result["flips"]] == [("005930", 3), ("000660", 2)]
    assert result["flips"][0]["name"] == "삼성전자"


def test_summary_window_excludes_older_rows(session):
    session.add_all([
        _change("005930", "BUY", days_ago=2),
        _change("005930", "HOLD", days_ago=45),
    ])
    session.commit()

    assert service.summary(session, days=30)["total"] == 1
    assert service.summary(session, days=90)["total"] == 2


def test_summary_recent_is_newest_first_and_capped(session):
    session.add_all([_change("005930", "BUY", days_ago=day) for day in range(1, 12)])
    session.commit()

    result = service.summary(session, days=30, limit=5)

    assert len(result["recent"]) == 5
    stamps = [row["recorded_at"] for row in result["recent"]]
    assert stamps == sorted(stamps, reverse=True)
    assert result["total"] == 11  # total 은 limit 과 무관하다


def test_summary_is_empty_without_history(session):
    result = service.summary(session)

    assert result == {"days": 30, "total": 0, "tickers": 0, "flips": [], "recent": []}
