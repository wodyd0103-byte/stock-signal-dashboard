"""신호 점수 + 보정 레이어 (심리/뉴스) 단위 테스트."""
from app.services.risk_service import RiskService
from app.services.signal_service import SignalService


def test_score_bounds(enriched):
    risk = RiskService().analyze("TEST", "1y", enriched)
    sig = SignalService().score(enriched, risk.risk_score)
    assert 0 <= sig.buy_score <= 100
    assert 0 <= sig.sell_score <= 100
    assert 0 <= sig.risk_score <= 100
    assert sig.signal in {"STRONG BUY", "BUY", "WEAK BUY", "HOLD", "WEAK SELL", "SELL", "STRONG SELL"}


def test_market_sentiment_fear_lowers_buy(enriched):
    svc = SignalService()
    base = svc.score(enriched, 30)
    fear = svc.score(enriched, 30, market_sentiment={"score": 15, "label": "극도 공포"})
    assert fear.final_buy_score <= base.final_buy_score


def test_news_positive_raises_buy(enriched):
    svc = SignalService()
    base = svc.score(enriched, 30)
    good = svc.score(enriched, 30, news_sentiment={"sentiment_score": 80, "label": "긍정"})
    assert good.final_buy_score >= base.final_buy_score


def test_news_negative_raises_sell(enriched):
    svc = SignalService()
    base = svc.score(enriched, 30)
    bad = svc.score(enriched, 30, news_sentiment={"sentiment_score": 20, "label": "부정"})
    assert bad.final_sell_score >= base.final_sell_score


def test_zones_consistent(enriched):
    svc = SignalService()
    assert svc.buy_score_zone(90) == "강한 매수 구간"
    assert svc.buy_score_zone(10) == "매수 부적합"
    assert svc.risk_score_zone(20) == "낮음"
    assert svc.risk_score_zone(90) == "매우 높음"
