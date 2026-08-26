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


def _change(ticker, current, *, name=None, days_ago=1, direction="up", kind="signal"):
    return SignalChange(
        ticker=ticker,
        name=name,
        current_signal=current,
        direction=direction,
        kind=kind,
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

    assert result == {"days": 30, "ticker": None, "total": 0, "tickers": 0, "flips": [], "recent": []}


# --- 종류 구분 -----------------------------------------------------------


def test_kind_is_stored(session):
    service.record_changes(
        session,
        [{"ticker": "005930", "current_signal": "18", "previous_signal": "1",
          "direction": "up", "kind": "score"}],
        datetime(2026, 8, 26, 8, 30),
    )

    assert session.query(SignalChange).one().kind == "score"


def test_the_same_day_can_hold_a_grade_change_and_a_score_move(session):
    at = datetime(2026, 8, 26, 8, 30)
    entries = [
        {"ticker": "005930", "current_signal": "BUY", "direction": "up", "kind": "signal"},
        {"ticker": "005930", "current_signal": "BUY", "direction": "up", "kind": "score"},
    ]

    # 중복 판정은 종류까지 본다 — 다른 종류면 같은 날에도 둘 다 남는다.
    assert service.record_changes(session, entries, at) == 2


def test_flip_counts_ignores_score_moves(session):
    session.add_all([
        _change("005930", "BUY", days_ago=1),
        _change("005930", "18", days_ago=2, kind="score"),
        _change("005930", "보통", days_ago=3, kind="risk"),
    ])
    session.commit()

    # 등급을 넘지 않은 움직임까지 세면 "몇 번 뒤집혔나"가 무슨 뜻인지 흐려진다.
    assert service.flip_counts(session, days=30) == {"005930": 1}


def test_summary_counts_only_grade_changes_as_flips(session):
    session.add_all([
        _change("005930", "BUY", name="삼성전자", days_ago=1),
        _change("005930", "HOLD", name="삼성전자", days_ago=2),
        _change("005930", "18", name="삼성전자", days_ago=3, kind="score"),
    ])
    session.commit()

    result = service.summary(session, days=30)

    assert result["total"] == 3  # 최근 목록에는 전부 나온다
    assert [(f["ticker"], f["count"]) for f in result["flips"]] == [("005930", 2)]
    assert {row["kind"] for row in result["recent"]} == {"signal", "score"}


def test_summary_can_narrow_to_one_ticker(session):
    session.add_all([
        _change("005930", "BUY", name="삼성전자", days_ago=1),
        _change("005930", "HOLD", name="삼성전자", days_ago=3),
        _change("000660", "SELL", name="SK하이닉스", days_ago=2),
    ])
    session.commit()

    result = service.summary(session, days=30, ticker="005930")

    assert result["ticker"] == "005930"
    assert result["total"] == 2
    assert [f["ticker"] for f in result["flips"]] == ["005930"]
    assert {row["ticker"] for row in result["recent"]} == {"005930"}


def test_summary_without_a_ticker_says_so(session):
    assert service.summary(session)["ticker"] is None


def test_a_ticker_with_one_flip_has_no_flips_entry(session):
    session.add_all([_change("005930", "BUY", days_ago=1)])
    session.commit()

    result = service.summary(session, ticker="005930")

    # 1회는 그 전환 자체라 셀 것이 없다.
    assert result["total"] == 1
    assert result["flips"] == []
