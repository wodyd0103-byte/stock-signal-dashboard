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
    n = svc.evaluate_due(db, lambda t: prices[t])
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
    assert svc.evaluate_due(db, lambda t: 200.0) == 0
