"""digest 수집 레이어 테스트 — 네트워크도 실 DB도 타지 않는다."""
from __future__ import annotations

from types import SimpleNamespace

import pandas as pd
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import app.database as database
from app.models.holding import Holding
from app.models.watchlist import WatchlistItem
import tools.digest.collector as collect_module


def _bundle(ticker: str, *, price: float, signal: str, final_buy: int, risk: int = 30):
    """analyze() 반환값 대역. Row가 실제로 읽는 필드만 채운다."""
    return SimpleNamespace(
        result=SimpleNamespace(ticker=ticker, market="KR"),
        enriched=pd.DataFrame(),
        quote={"current_price": price, "change_rate": 1.23},
        indicators=[],
        levels=None,
        risk=SimpleNamespace(risk_level="보통", risk_score=risk),
        prediction=None,
        signal=SimpleNamespace(
            signal=signal,
            buy_score=final_buy,
            sell_score=10,
            risk_score=risk,
            final_buy_score=final_buy,
            market_regime="SIDEWAYS",
            ml_up_probability=0.42,
            reasons=["테스트 사유"],
        ),
        market_sentiment=None,
        supply_demand=None,
        news_sentiment=None,
        sector=None,
        disclosure=None,
        fundamental=None,
        learned_signal=None,
    )


@pytest.fixture
def db_session(monkeypatch, tmp_path):
    """관심종목 2건 + 보유 2건. 005930은 양쪽에 있다."""
    engine = create_engine(
        f"sqlite:///{tmp_path / 'digest.db'}", connect_args={"check_same_thread": False}
    )
    TestSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    database.Base.metadata.create_all(bind=engine)

    session = TestSession()
    session.add_all([
        WatchlistItem(ticker="005930", name="삼성전자"),
        WatchlistItem(ticker="000660", name="SK하이닉스"),
        Holding(ticker="005930", name="삼성전자", quantity=10, avg_price=50_000),
        Holding(ticker="035720", name="카카오", quantity=5, avg_price=80_000),
    ])
    session.commit()
    session.close()

    monkeypatch.setattr(collect_module, "SessionLocal", TestSession)
    monkeypatch.setattr(collect_module.analysis_service, "market_sentiment_dict", lambda: {"score": 55})
    return TestSession


def test_load_targets_merges_a_ticker_held_and_watched(db_session):
    targets = {t.ticker: t for t in collect_module.load_targets()}

    assert set(targets) == {"005930", "000660", "035720"}
    assert sorted(targets["005930"].sources) == ["holdings", "watchlist"]
    assert targets["005930"].quantity == 10
    # 관심종목에만 있는 종목은 보유 수량이 없다
    assert targets["000660"].quantity is None


def test_load_targets_honours_the_source_filter(db_session):
    tickers = {t.ticker for t in collect_module.load_targets(["watchlist"])}
    assert tickers == {"005930", "000660"}


def test_collect_sorts_by_signal_strength_then_risk(db_session, monkeypatch):
    scores = {
        "005930": ("HOLD", 40),
        "000660": ("STRONG BUY", 90),
        "035720": ("WEAK BUY", 60),
    }

    def fake_analyze(ticker, period="1y"):
        signal, final_buy = scores[ticker]
        return _bundle(ticker, price=60_000, signal=signal, final_buy=final_buy)

    monkeypatch.setattr(collect_module.analysis_service, "analyze", fake_analyze)

    digest = collect_module.collect()

    assert [r.ticker for r in digest.rows] == ["000660", "035720", "005930"]
    assert digest.failures == []
    assert digest.market_sentiment == {"score": 55}


def test_collect_computes_pnl_for_holdings_only(db_session, monkeypatch):
    monkeypatch.setattr(
        collect_module.analysis_service,
        "analyze",
        lambda ticker, period="1y": _bundle(ticker, price=60_000, signal="HOLD", final_buy=40),
    )

    rows = {r.ticker: r for r in collect_module.collect().rows}

    # 50,000 에 사서 60,000 → +20%
    assert rows["005930"].pnl_pct == 20.0
    assert rows["035720"].pnl_pct == -25.0  # 80,000 → 60,000
    assert rows["000660"].pnl_pct is None


def test_collect_keeps_going_when_one_ticker_fails(db_session, monkeypatch):
    def flaky_analyze(ticker, period="1y"):
        if ticker == "000660":
            raise RuntimeError("provider 죽음")
        return _bundle(ticker, price=60_000, signal="HOLD", final_buy=40)

    monkeypatch.setattr(collect_module.analysis_service, "analyze", flaky_analyze)

    digest = collect_module.collect()

    assert {r.ticker for r in digest.rows} == {"005930", "035720"}
    assert [f.ticker for f in digest.failures] == ["000660"]
    assert "provider 죽음" in digest.failures[0].error
    assert digest.total == 3


def test_collect_returns_empty_digest_without_targets(db_session, monkeypatch):
    monkeypatch.setattr(collect_module, "load_targets", lambda sources=None: [])

    digest = collect_module.collect()

    assert digest.rows == []
    assert digest.failures == []
    assert digest.total == 0
