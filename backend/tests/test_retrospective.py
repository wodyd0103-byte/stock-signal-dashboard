"""회고 기록/채점 로직 (in-memory SQLite)."""
from datetime import datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models.recommendation import Recommendation
from app.services.retrospective_service import RetrospectiveService


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    s = Session()
    yield s
    s.close()


def test_record_only_buy_signals(db):
    svc = RetrospectiveService()
    assert svc.record(db, ticker="A", name=None, market="KR", signal="HOLD", buy_score=40, risk_score=50, price=100) is None
    rec = svc.record(db, ticker="A", name=None, market="KR", signal="BUY", buy_score=78, risk_score=40, price=100)
    assert rec is not None and rec.status == "open"


def test_record_dedup_24h(db):
    svc = RetrospectiveService()
    r1 = svc.record(db, ticker="B", name=None, market="KR", signal="BUY", buy_score=78, risk_score=40, price=100)
    r2 = svc.record(db, ticker="B", name=None, market="KR", signal="BUY", buy_score=80, risk_score=35, price=105)
    assert r1.id == r2.id  # 중복 → 같은 레코드


def test_evaluate_hit_and_miss(db):
    svc = RetrospectiveService()
    # 6일 전 추천 2건
    for tk, p in [("WIN", 100.0), ("LOSE", 100.0)]:
        db.add(Recommendation(ticker=tk, signal="BUY", buy_score=80, risk_score=40,
                              price_at_rec=p, horizon_days=5, status="open",
                              recommended_at=datetime.utcnow() - timedelta(days=6)))
    db.commit()
    prices = {"WIN": 110.0, "LOSE": 90.0}
    n = svc.evaluate_due(db, lambda t, due: prices[t])
    assert n == 2
    s = svc.summary(db)
    assert s["evaluated"] == 2
    assert s["hit_rate"] == 0.5  # 1승 1패


def test_evaluate_skips_not_due(db):
    svc = RetrospectiveService()
    db.add(Recommendation(ticker="C", signal="BUY", buy_score=80, risk_score=40,
                          price_at_rec=100, horizon_days=5, status="open",
                          recommended_at=datetime.utcnow()))  # 오늘 → 미도래
    db.commit()
    assert svc.evaluate_due(db, lambda t, due: 200.0) == 0


def test_evaluate_asks_for_the_price_at_the_horizon(db):
    """늦게 채점해도 5일 성과는 5일 성과여야 한다.

    현재가로 재면 밀린 추천일수록 수익률이 부풀어 오르고, 적중률과 평균수익이
    그 위에 쌓인다.
    """
    svc = RetrospectiveService()
    recommended = datetime.utcnow() - timedelta(days=71)
    db.add(Recommendation(ticker="OLD", signal="BUY", buy_score=80, risk_score=40,
                          price_at_rec=100.0, horizon_days=5, status="open",
                          recommended_at=recommended))
    db.commit()

    asked = []

    def price(ticker, due):
        asked.append(due)
        return 104.0

    assert svc.evaluate_due(db, price) == 1
    assert asked == [(recommended + timedelta(days=5)).date()]
    assert db.query(Recommendation).filter_by(ticker="OLD").one().return_pct == 4.0
