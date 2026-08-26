"""digest 실행 시 회고 채점 — 네트워크 없이 배선만 본다."""
from __future__ import annotations

from datetime import date, datetime, timedelta

import pandas as pd
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import app.database as database
from app.models.recommendation import Recommendation
from app.services import analysis_service
from app.services.data_provider import StockDataProvider
from app.services.retrospective_service import RetrospectiveService
from tools.digest import retro


@pytest.fixture
def session(tmp_path):
    engine = create_engine(
        f"sqlite:///{tmp_path / 'retro.db'}", connect_args={"check_same_thread": False}
    )
    database.Base.metadata.create_all(bind=engine)
    db = sessionmaker(bind=engine)()
    yield db
    db.close()


def _recommendation(ticker="005930", *, days_ago=30, horizon=5, price=100_000.0, status="open"):
    return Recommendation(
        ticker=ticker,
        name=ticker,
        market="KR",
        signal="BUY",
        buy_score=70,
        risk_score=30,
        price_at_rec=price,
        horizon_days=horizon,
        status=status,
        recommended_at=datetime.utcnow() - timedelta(days=days_ago),
    )


# --- 시점 종가 -----------------------------------------------------------


def _frame(rows):
    return pd.DataFrame([{"date": d, "close": c} for d, c in rows])


def test_latest_close_reads_the_last_bar(monkeypatch):
    frame = pd.DataFrame({"close": [90.0, 110.0]})
    # 싱글턴 인스턴스가 아니라 클래스를 갈아끼운다. 인스턴스에 속성을 심으면
    # monkeypatch 가 teardown 에서 그 자리에 바운드 메서드를 되돌려 놓고,
    # 이후 다른 테스트의 클래스 레벨 패치가 그 인스턴스에서만 가려진다.
    monkeypatch.setattr(
        StockDataProvider,
        "fetch_ohlcv",
        lambda self, ticker, period: type("R", (), {"data": frame})(),
    )

    assert analysis_service.latest_close("005930") == 110.0


def test_latest_close_returns_none_when_the_provider_fails(monkeypatch):
    def explode(self, ticker, period):
        raise RuntimeError("provider 죽음")

    monkeypatch.setattr(StockDataProvider, "fetch_ohlcv", explode)

    # 채점이 못 되는 것과 리포트가 죽는 것은 다르다.
    assert analysis_service.latest_close("005930") is None


def test_latest_close_returns_none_on_an_empty_frame(monkeypatch):
    monkeypatch.setattr(
        StockDataProvider,
        "fetch_ohlcv",
        lambda self, ticker, period: type("R", (), {"data": pd.DataFrame()})(),
    )

    assert analysis_service.latest_close("005930") is None


def test_close_on_takes_the_price_of_that_day(monkeypatch):
    frame = _frame([("2026-08-20", 100.0), ("2026-08-21", 105.0), ("2026-08-24", 130.0)])
    monkeypatch.setattr(
        StockDataProvider, "fetch_ohlcv", lambda self, ticker, period: type("R", (), {"data": frame})()
    )

    # 현재가(130)가 아니라 그 날짜(21일)의 종가를 쓴다.
    assert analysis_service.close_on("005930", date(2026, 8, 21)) == 105.0


def test_close_on_rolls_forward_over_a_market_holiday(monkeypatch):
    frame = _frame([("2026-08-21", 105.0), ("2026-08-24", 130.0)])
    monkeypatch.setattr(
        StockDataProvider, "fetch_ohlcv", lambda self, ticker, period: type("R", (), {"data": frame})()
    )

    # 22일(토)은 휴장 — 다음 거래일 종가로 본다.
    assert analysis_service.close_on("005930", date(2026, 8, 22)) == 130.0


def test_close_on_returns_none_past_the_last_bar(monkeypatch):
    frame = _frame([("2026-08-21", 105.0)])
    monkeypatch.setattr(
        StockDataProvider, "fetch_ohlcv", lambda self, ticker, period: type("R", (), {"data": frame})()
    )

    # 그 날 이후 거래일이 없으면 horizon 이 안 지난 셈이라 채점하지 않는다.
    assert analysis_service.close_on("005930", date.today()) is None


def test_close_on_refuses_a_future_date(monkeypatch):
    def explode(self, ticker, period):
        raise AssertionError("미래 날짜는 조회조차 하지 않는다")

    monkeypatch.setattr(StockDataProvider, "fetch_ohlcv", explode)

    assert analysis_service.close_on("005930", date.today() + timedelta(days=3)) is None


def test_the_period_grows_with_the_gap(monkeypatch):
    asked: list[str] = []
    frame = _frame([("2026-08-21", 105.0)])

    def record(self, ticker, period):
        asked.append(period)
        return type("R", (), {"data": frame})()

    monkeypatch.setattr(StockDataProvider, "fetch_ohlcv", record)

    analysis_service.close_on("005930", date.today() - timedelta(days=5))
    analysis_service.close_on("005930", date.today() - timedelta(days=200))

    # 짧을수록 조회가 가볍다. 닿는 만큼만 요청한다.
    assert asked == ["1mo", "1y"]


# --- 채점 ----------------------------------------------------------------


def test_a_due_recommendation_is_scored(session, monkeypatch):
    session.add(_recommendation(price=100_000.0))
    session.commit()
    monkeypatch.setattr(retro, "close_on", lambda ticker, due: 120_000.0)

    count, error = retro.evaluate(session)

    assert (count, error) == (1, None)
    row = session.query(Recommendation).one()
    assert (row.status, row.return_pct, row.hit) == ("evaluated", 20.0, 1)


def test_a_recommendation_inside_its_horizon_waits(session, monkeypatch):
    session.add(_recommendation(days_ago=1, horizon=5))
    session.commit()
    monkeypatch.setattr(retro, "close_on", lambda ticker, due: 120_000.0)

    count, _ = retro.evaluate(session)

    assert count == 0
    assert session.query(Recommendation).one().status == "open"


def test_a_loss_is_recorded_as_a_miss(session, monkeypatch):
    session.add(_recommendation(price=100_000.0))
    session.commit()
    monkeypatch.setattr(retro, "close_on", lambda ticker, due: 80_000.0)

    retro.evaluate(session)

    row = session.query(Recommendation).one()
    assert (row.return_pct, row.hit) == (-20.0, 0)


def test_a_missing_price_leaves_the_recommendation_open(session, monkeypatch):
    session.add(_recommendation())
    session.commit()
    monkeypatch.setattr(retro, "close_on", lambda ticker, due: None)

    count, error = retro.evaluate(session)

    # 값을 못 받았다고 0%로 채점하면 통계가 거짓말을 한다.
    assert (count, error) == (0, None)
    assert session.query(Recommendation).one().status == "open"


def test_a_crash_is_reported_without_raising(session, monkeypatch):
    def explode(self, db, price_fn):
        raise RuntimeError("DB 잠김")

    monkeypatch.setattr(RetrospectiveService, "evaluate_due", explode)

    count, error = retro.evaluate(session)

    assert count == 0
    assert "회고 채점 실패" in error


def test_nothing_to_score_is_not_an_error(session, monkeypatch):
    monkeypatch.setattr(retro, "close_on", lambda ticker, due: 120_000.0)

    assert retro.evaluate(session) == (0, None)


def test_scoring_uses_the_horizon_date_not_today(session, monkeypatch):
    """늦게 채점해도 5일 성과는 5일 성과여야 한다."""
    session.add(_recommendation(days_ago=71, horizon=5, price=100_000.0))
    session.commit()

    asked: list[date] = []

    def price(ticker, due):
        asked.append(due)
        return 105_000.0  # horizon 시점 가격

    monkeypatch.setattr(retro, "close_on", price)

    retro.evaluate(session)

    row = session.query(Recommendation).one()
    assert row.return_pct == 5.0  # 71일 수익률이 아니라 5일 수익률
    assert asked[0] == (datetime.utcnow() - timedelta(days=71) + timedelta(days=5)).date()
