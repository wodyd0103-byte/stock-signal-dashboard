"""라우터 스모크 테스트 — 모든 엔드포인트가 실제로 붙어 있고 계약을 지키는지.

서비스 로직은 다른 파일들이 이미 본다. 여기서 보는 것은 배선이다:
라우터가 등록됐는지, 상태코드가 맞는지, 응답에 프론트가 읽는 키가 있는지,
DataProviderError 가 HTTP 로 옳게 번역되는지, DB 쓰기 엔드포인트가 실제로
쓰고 지우는지.

네트워크와 실 DB 는 타지 않는다. `StockDataProvider.fetch_ohlcv` 를 클래스에서
갈아끼우므로 따로 만든 provider 싱글턴이 몇 개든 한 번에 덮인다.
DB 는 tmp_path 의 SQLite 로 돌리고, `get_db` 의존성과 `SessionLocal` 을 둘 다
바꿔서 `backend/quant_app.db` 에는 손대지 않는다.
"""
import csv
import io

import pandas as pd
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from conftest import make_ohlcv

from app.core.config import Settings
from app.services.data_provider import (
    PERIOD_TO_DAYS,
    DataProviderError,
    PriceDataResult,
    StockDataProvider,
)


FAILING_TICKER = "999999"

UNIVERSE = [
    {"name": "삼성전자", "ticker": "005930", "market": "KR"},
    {"name": "SK하이닉스", "ticker": "000660", "market": "KR"},
    {"name": "Apple", "ticker": "AAPL", "market": "US"},
]

SIGNALS = {"STRONG BUY", "BUY", "WEAK BUY", "HOLD", "WEAK SELL", "SELL", "STRONG SELL"}


ROWS_1Y = 260  # PERIOD_TO_DAYS["1y"] 를 영업일로 환산한 값


def _rows_for(period: str) -> int:
    """진짜 provider 처럼 기간에 비례한 길이를 돌려준다 — 달력일 → 영업일."""
    return PERIOD_TO_DAYS.get(period, 365) * 5 // 7


def _frame_for(ticker: str, period: str) -> pd.DataFrame:
    """티커마다 다른 시계열 — 순위/정렬이 전부 동점이면 검사가 무의미해진다."""
    seed = sum(ord(ch) for ch in ticker) % 97
    frame = make_ohlcv(n=_rows_for(period), seed=seed, trend=(seed % 5 - 2) * 0.2)
    frame["date"] = pd.to_datetime(frame["date"]).dt.date
    return frame


def _fake_fetch(self, ticker, period="1y", *, force_refresh=False):
    """정규화·시장판별은 진짜를 쓰고 네트워크 호출만 대체한다."""
    normalized = self.normalize_ticker(ticker)
    market = self.detect_market(normalized)
    if normalized == FAILING_TICKER:
        raise DataProviderError(
            "pykrx: 502; FinanceDataReader: timeout",
            ticker=normalized,
            market=market,
            selected_provider="KoreanStockDataProvider",
            source="none",
            error_type="all_providers_failed",
            providers_tried=[
                {"name": "pykrx", "status": "error", "error": "502"},
                {"name": "FinanceDataReader", "status": "error", "error": "timeout"},
            ],
        )
    return PriceDataResult(
        ticker=normalized,
        market=market,
        source="pykrx" if market == "KR" else "yfinance",
        is_sample=False,
        provider_status="success",
        provider_message="실제 데이터를 정상 조회했습니다.",
        data=_frame_for(normalized, period),
        selected_provider="KoreanStockDataProvider" if market == "KR" else "YahooDataProvider",
        providers_tried=[{"name": "pykrx", "status": "success", "rows": _rows_for(period)}],
    )


class _FakeSentiment:
    def to_dict(self):
        return {"score": 55, "label": "중립", "components": []}


class _FakeSentimentService:
    def get(self, force_refresh=False):
        return _FakeSentiment()


class _FakeSurgePrediction:
    surge_probability = 0.42
    base_rate = 0.2
    lift = 2.1
    cv_score = 0.61
    train_samples = 180
    train_positive = 36
    upper_pct = 10.0
    horizon_days = 10
    reasons = ["거래량 급증", "20일 신고가 근접"]


@pytest.fixture
def client(monkeypatch, tmp_path):
    import app.database as database
    from app.main import app
    from app.services import scan_service, surge_scan_service

    engine = create_engine(
        f"sqlite:///{tmp_path / 'test.db'}", connect_args={"check_same_thread": False}
    )
    TestSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    # init_db 는 startup 이벤트에서만 도는데 TestClient 를 컨텍스트 매니저로 쓰지
    # 않으므로 실행되지 않는다(스케줄러도 같이 안 뜬다). 테이블은 직접 만든다.
    from app.models.holding import Holding  # noqa: F401
    from app.models.recommendation import Recommendation  # noqa: F401
    from app.models.signal_change import SignalChange  # noqa: F401
    from app.models.watchlist import WatchlistItem  # noqa: F401

    database.Base.metadata.create_all(bind=engine)

    def override_get_db():
        db = TestSession()
        try:
            yield db
        finally:
            db.close()

    # 의존성 오버라이드가 정규 경로. SessionLocal 교체는 이를 우회하는 코드가
    # 생기더라도 실 DB 로 새지 않게 하는 안전망이다.
    monkeypatch.setattr(database, "SessionLocal", TestSession)
    app.dependency_overrides[database.get_db] = override_get_db

    monkeypatch.setattr(Settings, "ALLOW_SAMPLE_FALLBACK", False)
    monkeypatch.setattr(Settings, "BUY_SIGNAL_ITEM_TIMEOUT_SECONDS", 30)
    monkeypatch.setattr(StockDataProvider, "fetch_ohlcv", _fake_fetch)

    # 대표 종목 수집은 네트워크를 탄다. 세 종목으로 고정.
    from app.services.universe_service import UniverseResult, UniverseService

    def fake_universe(self, market="all", kr_limit=100, us_limit=100, source="auto", *, force_refresh=False):
        items = [item for item in UNIVERSE if market == "all" or item["market"] == market]
        return UniverseResult(
            market=market,
            source="fallback",
            items=items,
            kr_count=len([i for i in items if i["market"] == "KR"]),
            us_count=len([i for i in items if i["market"] == "US"]),
            updated_at=pd.Timestamp("2026-08-18T00:00:00").to_pydatetime(),
        )

    monkeypatch.setattr(UniverseService, "get_representative_stocks", fake_universe)

    # 분석 응답에 붙는 외부 조회(네이버 수급/뉴스/공시/업종/재무)는 전부 끈다.
    # 시장심리만 값을 돌려줘 배선이 살아있는지 볼 수 있게 남긴다.
    from app.services import analysis_service

    monkeypatch.setattr(analysis_service, "market_sentiment_dict", lambda: {"score": 55, "label": "중립"})
    for name in ("supply_demand_dict", "news_sentiment_dict", "sector_dict", "disclosure_dict", "fundamental_dict"):
        monkeypatch.setattr(analysis_service, name, lambda ticker: None)
    monkeypatch.setattr(analysis_service._learned_service, "score", lambda enriched: None)

    import app.services.market_sentiment_service as sentiment_module

    monkeypatch.setattr(sentiment_module, "MarketSentimentService", _FakeSentimentService)

    from app.services.surge_predictor import SurgePredictor

    monkeypatch.setattr(SurgePredictor, "predict", lambda self, enriched: _FakeSurgePrediction())

    # 라우터 모듈 캐시는 프로세스 수명 내내 살아있다. 테스트끼리 새지 않게 비운다.
    scan_service.clear_caches()
    surge_scan_service.clear_cache()

    # 컨텍스트 매니저로 열지 않는다 — startup 이벤트가 돌면 실 DB 로 init_db 하고
    # APScheduler 까지 뜬다. 미들웨어와 라우팅은 그대로 동작한다.
    yield TestClient(app)

    app.dependency_overrides.clear()
    scan_service.clear_caches()
    surge_scan_service.clear_cache()


@pytest.fixture
def forced_buy_signal(monkeypatch):
    """신호를 BUY 로 고정한다.

    합성 랜덤워크로는 매수 신호가 나오지 않는다 — trend 와 seed 를 훑어도
    buy_score 최대 40, 전부 HOLD 였다. 그래서 "매수면 기록한다" 쪽 분기를
    데이터로는 켤 수 없다. 이 테스트들의 대상은 신호 엔진의 판정이 아니라
    기록·중복방지 배선이므로 신호를 고정한다.
    """
    from app.services import analysis_service

    real_score = analysis_service.signal_service.score

    def forced(*args, **kwargs):
        return real_score(*args, **kwargs).model_copy(update={"signal": "BUY"})

    monkeypatch.setattr(analysis_service.signal_service, "score", forced)


def _csv_rows(response):
    text = response.text.lstrip("﻿")
    return list(csv.reader(io.StringIO(text)))


# --- 앱 배선 -------------------------------------------------------------


def test_health(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "quant-insight-api"}


def test_request_id_header_is_set(client):
    # main.py 의 로깅 미들웨어가 붙어 있는지. 없으면 조용히 사라지는 종류의 배선.
    response = client.get("/api/health")
    assert len(response.headers["X-Request-ID"]) == 8


@pytest.mark.parametrize(
    "path",
    [
        "/api/stocks/{ticker}/price",
        "/api/stocks/{ticker}/indicators",
        "/api/stocks/{ticker}/prediction",
        "/api/stocks/{ticker}/signal",
        "/api/stocks/{ticker}/analysis",
        "/api/stocks/{ticker}/backtest",
        "/api/market/sentiment",
        "/api/market/representative-stocks",
        "/api/market/buy-signals",
        "/api/market/compare",
        "/api/watchlist",
        "/api/watchlist/{ticker}",
        "/api/portfolio/holdings",
        "/api/portfolio/analysis",
        "/api/portfolio/rebalance",
        "/api/portfolio/optimize",
        "/api/surge/scan",
        "/api/surge/{ticker}",
        "/api/ic/factors",
        "/api/retrospective/summary",
        "/api/retrospective/evaluate",
        "/api/retrospective/signal-changes",
        "/api/export/buy-signals.csv",
        "/api/export/watchlist.csv",
        "/api/export/stock/{ticker}.csv",
        "/api/debug/data-provider/{ticker}",
    ],
)
def test_route_is_registered(client, path):
    # main.py 에서 include_router 한 줄이 빠지면 여기서 걸린다. README 의 API 표와 같은 목록.
    assert path in client.app.openapi()["paths"]


def test_unknown_path_is_404(client):
    assert client.get("/api/stocks").status_code == 404


# --- stock_router --------------------------------------------------------


def test_price(client):
    response = client.get("/api/stocks/005930/price")
    assert response.status_code == 200
    body = response.json()
    assert body["ticker"] == "005930"
    assert body["source"] == "pykrx"
    assert body["is_sample"] is False
    assert len(body["prices"]) == ROWS_1Y
    assert body["prices"] == body["data"]  # 프론트가 둘 중 하나를 읽는다
    assert body["prices"][-1]["ma20"] is not None


def test_price_resolves_korean_alias(client):
    response = client.get("/api/stocks/삼성전자/price")
    assert response.status_code == 200
    assert response.json()["ticker"] == "005930"


def test_indicators(client):
    response = client.get("/api/stocks/005930/indicators")
    assert response.status_code == 200
    body = response.json()
    assert body["indicators"]
    assert "levels" in body


def test_prediction(client):
    response = client.get("/api/stocks/005930/prediction")
    assert response.status_code == 200
    body = response.json()
    assert body["predictions"]
    assert {p["horizon_days"] for p in body["predictions"]}


def test_signal(client):
    response = client.get("/api/stocks/005930/signal")
    assert response.status_code == 200
    body = response.json()
    assert body["signal"] in SIGNALS
    assert 0 <= body["buy_score"] <= 100
    assert 0 <= body["risk_score"] <= 100


def test_analysis(client):
    response = client.get("/api/stocks/005930/analysis")
    assert response.status_code == 200
    body = response.json()
    assert body["signal"]["signal"] in SIGNALS
    assert body["indicators"]
    assert body["risk"]
    assert len(body["price_history"]) == ROWS_1Y
    assert body["market_sentiment"] == {"score": 55, "label": "중립"}
    assert "투자 판단과 책임은 사용자 본인" in body["disclaimer"]


def test_backtest(client):
    # 6mo 로 돌린다. 백테스트는 바마다 재평가라 1y(260봉)면 20초를 넘는데,
    # 스모크 테스트가 확인할 것(배선·비용 반영)은 길이와 무관하다.
    response = client.get("/api/stocks/005930/backtest?period=6mo&initial_capital=5000000")
    assert response.status_code == 200
    body = response.json()
    assert body["trade_count"] >= 0
    assert "거래세" in body["note"]


def test_backtest_rejects_tiny_capital(client):
    assert client.get("/api/stocks/005930/backtest?initial_capital=1000").status_code == 422


def test_period_reaches_the_provider(client):
    # 쿼리의 period 가 provider 호출까지 내려가는지. 길이가 안 바뀌면 어딘가에서 먹힌 것.
    one_year = client.get("/api/stocks/005930/price?period=1y").json()
    six_months = client.get("/api/stocks/005930/price?period=6mo").json()
    assert len(one_year["prices"]) == ROWS_1Y
    assert len(six_months["prices"]) == PERIOD_TO_DAYS["6mo"] * 5 // 7
    assert six_months["period"] == "6mo"


def test_unknown_period_is_422(client):
    # Period 는 Literal["1mo","3mo","6mo","1y","3y"]. "1m" 은 provider 쪽 표기라 통하면 안 된다.
    assert client.get("/api/stocks/005930/price?period=1m").status_code == 422


def test_provider_failure_is_502_with_the_chain(client):
    response = client.get(f"/api/stocks/{FAILING_TICKER}/price")
    assert response.status_code == 502
    detail = response.json()["detail"]
    assert detail["error_type"] == "all_providers_failed"
    assert [item["name"] for item in detail["providers_tried"]] == ["pykrx", "FinanceDataReader"]
    assert detail["is_sample"] is False


def test_invalid_ticker_is_400(client):
    # 형식 오류는 사용자 잘못이라 502(업스트림 탓)가 아니라 400 이어야 한다.
    response = client.get("/api/stocks/없는종목/price")
    assert response.status_code == 400
    assert response.json()["detail"]["error_type"] == "invalid_ticker_format"


def test_debug_data_provider(client):
    response = client.get("/api/debug/data-provider/005930")
    assert response.status_code == 200
    body = response.json()
    assert body["normalized_ticker"] == "005930"
    assert body["final_source"] == "pykrx"


def test_debug_data_provider_reports_failure_as_200(client):
    # 디버그 엔드포인트는 실패를 payload 로 돌려준다. 502 로 끊으면 진단이 안 된다.
    response = client.get(f"/api/debug/data-provider/{FAILING_TICKER}")
    assert response.status_code == 200
    assert response.json()["error_type"] == "all_providers_failed"


# --- market_router -------------------------------------------------------


def test_representative_stocks(client):
    response = client.get("/api/market/representative-stocks")
    assert response.status_code == 200
    body = response.json()
    assert body["total_count"] == len(UNIVERSE)
    assert body["kr_count"] == 2
    assert body["us_count"] == 1
    assert body["source"] == "fallback"


def test_market_sentiment(client):
    response = client.get("/api/market/sentiment")
    assert response.status_code == 200
    assert response.json()["label"] == "중립"


def test_buy_signals(client):
    response = client.get("/api/market/buy-signals?min_signal=WEAK_BUY&limit=10")
    assert response.status_code == 200
    body = response.json()
    assert body["total_checked"] == len(UNIVERSE)
    assert body["total_failed"] == 0
    assert body["failed_items"] == []
    assert [item["rank"] for item in body["items"]] == list(range(1, len(body["items"]) + 1))
    for item in body["items"]:
        assert item["signal"] in {"STRONG BUY", "BUY", "WEAK BUY"}


def test_buy_signals_keeps_going_when_one_ticker_fails(client, monkeypatch):
    from app.services.universe_service import UniverseResult, UniverseService

    broken = UNIVERSE + [{"name": "없는회사", "ticker": FAILING_TICKER, "market": "KR"}]
    monkeypatch.setattr(
        UniverseService,
        "get_representative_stocks",
        lambda self, **kwargs: UniverseResult(
            market="all", source="fallback", items=broken, kr_count=3, us_count=1,
            updated_at=pd.Timestamp("2026-08-18").to_pydatetime(),
        ),
    )
    response = client.get("/api/market/buy-signals?force_refresh=true")
    assert response.status_code == 200
    body = response.json()
    assert body["total_checked"] == 4
    assert [item["ticker"] for item in body["failed_items"]] == [FAILING_TICKER]
    assert body["total_success"] == 3


def test_compare(client):
    response = client.get("/api/market/compare?tickers=005930,000660,AAPL")
    assert response.status_code == 200
    items = response.json()["items"]
    assert [item["ticker"] for item in items] == ["005930", "000660", "AAPL"]
    for item in items:
        assert item["signal"] in SIGNALS


def test_compare_dedupes_and_needs_two(client):
    response = client.get("/api/market/compare?tickers=005930,삼성전자")
    assert response.status_code == 200
    body = response.json()
    assert body["items"] == []
    assert "2~4개" in body["error"]


# --- watchlist_router (DB) ------------------------------------------------


def test_watchlist_crud(client):
    assert client.get("/api/watchlist").json() == []

    created = client.post("/api/watchlist", json={"ticker": "삼성전자", "name": "삼성전자"})
    assert created.status_code == 201
    assert created.json()["ticker"] == "005930"  # 별칭이 정규화돼 저장된다

    listed = client.get("/api/watchlist").json()
    assert len(listed) == 1
    assert listed[0]["ticker"] == "005930"
    assert listed[0]["signal"] in SIGNALS
    assert listed[0]["error"] is None

    deleted = client.delete("/api/watchlist/005930")
    assert deleted.status_code == 204
    assert client.get("/api/watchlist").json() == []


def test_watchlist_duplicate_returns_the_same_row(client):
    first = client.post("/api/watchlist", json={"ticker": "005930"}).json()
    second = client.post("/api/watchlist", json={"ticker": "005930.KS"}).json()
    assert first["id"] == second["id"]
    assert len(client.get("/api/watchlist").json()) == 1


def test_watchlist_summary_reports_per_item_failure(client):
    # 한 종목이 죽어도 목록 전체가 500 이 되면 안 된다.
    client.post("/api/watchlist", json={"ticker": FAILING_TICKER})
    body = client.get("/api/watchlist").json()
    assert len(body) == 1
    assert body[0]["signal"] is None
    assert body[0]["error"]


def test_watchlist_delete_missing_is_404(client):
    assert client.delete("/api/watchlist/005930").status_code == 404


def test_watchlist_rejects_empty_ticker(client):
    assert client.post("/api/watchlist", json={"ticker": ""}).status_code == 422


# --- portfolio_router (DB) ------------------------------------------------


def test_holdings_crud(client):
    assert client.get("/api/portfolio/holdings").json() == []

    created = client.post(
        "/api/portfolio/holdings",
        json={"ticker": "005930", "name": "삼성전자", "quantity": 10, "avg_price": 70000},
    )
    assert created.status_code == 201
    assert created.json()["quantity"] == 10

    assert len(client.get("/api/portfolio/holdings").json()) == 1
    assert client.delete("/api/portfolio/holdings/005930").status_code == 204
    assert client.get("/api/portfolio/holdings").json() == []


def test_holdings_rebuy_averages_the_price(client):
    client.post("/api/portfolio/holdings", json={"ticker": "005930", "quantity": 10, "avg_price": 70000})
    again = client.post("/api/portfolio/holdings", json={"ticker": "005930", "quantity": 10, "avg_price": 80000})
    body = again.json()
    assert body["quantity"] == 20
    assert body["avg_price"] == 75000
    assert len(client.get("/api/portfolio/holdings").json()) == 1


def test_holdings_reject_non_positive_quantity(client):
    response = client.post(
        "/api/portfolio/holdings", json={"ticker": "005930", "quantity": 0, "avg_price": 70000}
    )
    assert response.status_code == 422


def test_holdings_delete_missing_is_404(client):
    assert client.delete("/api/portfolio/holdings/005930").status_code == 404


def test_portfolio_analysis(client):
    client.post("/api/portfolio/holdings", json={"ticker": "005930", "quantity": 10, "avg_price": 70000})
    client.post("/api/portfolio/holdings", json={"ticker": "000660", "quantity": 5, "avg_price": 150000})
    response = client.get("/api/portfolio/analysis")
    assert response.status_code == 200
    body = response.json()
    assert len(body["holdings"]) == 2
    assert body["total_value"] > 0


def test_portfolio_rebalance(client):
    client.post("/api/portfolio/holdings", json={"ticker": "005930", "quantity": 10, "avg_price": 70000})
    client.post("/api/portfolio/holdings", json={"ticker": "000660", "quantity": 5, "avg_price": 150000})
    response = client.get("/api/portfolio/rebalance?cash=1000000&strategy=equal")
    assert response.status_code == 200
    body = response.json()
    assert body["strategy"] == "equal"
    assert body["cash"] == 1000000
    trades = body["trades"]
    assert {t["ticker"] for t in trades} == {"005930", "000660"}
    assert [t["target_weight"] for t in trades] == [50.0, 50.0]  # equal = 균등
    for trade in trades:
        assert trade["action"] in {"buy", "sell", "hold"}
    assert body["est_cost_total"] >= 0


def test_portfolio_rebalance_rejects_unknown_strategy(client):
    assert client.get("/api/portfolio/rebalance?strategy=moon").status_code == 422


def test_portfolio_optimize(client):
    client.post("/api/portfolio/holdings", json={"ticker": "005930", "quantity": 10, "avg_price": 70000})
    client.post("/api/portfolio/holdings", json={"ticker": "000660", "quantity": 5, "avg_price": 150000})
    response = client.get("/api/portfolio/optimize?method=min_variance")
    assert response.status_code == 200


def test_portfolio_optimize_needs_two_tickers(client):
    client.post("/api/portfolio/holdings", json={"ticker": "005930", "quantity": 10, "avg_price": 70000})
    assert "error" in client.get("/api/portfolio/optimize").json()


# --- surge_router ---------------------------------------------------------


def test_surge_single(client):
    response = client.get("/api/surge/005930")
    assert response.status_code == 200
    body = response.json()
    assert body["ticker"] == "005930"
    assert body["surge_probability"] == 0.42
    assert body["signal_label"] == "강함"  # prob 0.42, lift 2.1 → classify_signal


def test_surge_scan(client):
    response = client.get("/api/surge/scan?market=KR&kr_limit=10")
    assert response.status_code == 200
    body = response.json()
    assert body["total_scanned"] == 2  # 유니버스의 KR 두 종목
    assert [item["rank"] for item in body["items"]] == [1, 2]
    assert body["failed"] == []


def test_surge_scan_filters_by_probability(client):
    response = client.get("/api/surge/scan?market=KR&min_probability=0.9")
    assert response.status_code == 200
    body = response.json()
    assert body["items"] == []
    assert body["total_scanned"] == 2  # 스캔은 했고 필터에서 걸린 것


def test_surge_single_failure_is_400(client):
    response = client.get(f"/api/surge/{FAILING_TICKER}")
    assert response.status_code == 400
    assert "502" in response.json()["detail"]


# --- ic / retrospective ---------------------------------------------------


def test_ic_factors(client, monkeypatch):
    from app.services.ic_service import FactorIC, ICReport, ICService

    report = ICReport(
        horizon_days=5,
        universe_size=3,
        factors=[FactorIC("rsi", "RSI", 0.11, 0.9, 0.6, 12, "보통")],
        updated_at="2026-08-18T00:00:00",
        note="테스트",
    )
    monkeypatch.setattr(ICService, "compute", lambda self, h, u, force=False: report)

    response = client.get("/api/ic/factors?horizon_days=5&universe_size=20")
    assert response.status_code == 200
    body = response.json()
    assert body["factors"][0]["factor"] == "rsi"
    assert body["horizon_days"] == 5


def test_ic_factors_validates_range(client):
    assert client.get("/api/ic/factors?horizon_days=99").status_code == 422
    assert client.get("/api/ic/factors?universe_size=5").status_code == 422


def test_retrospective_summary_on_empty_db(client):
    response = client.get("/api/retrospective/summary")
    assert response.status_code == 200
    assert isinstance(response.json(), dict)


def test_retrospective_evaluate(client):
    response = client.post("/api/retrospective/evaluate")
    assert response.status_code == 200
    assert response.json()["evaluated"] == 0


def test_signal_changes_on_empty_db(client):
    response = client.get("/api/retrospective/signal-changes")

    assert response.status_code == 200
    body = response.json()
    assert body == {"days": 30, "ticker": None, "total": 0, "tickers": 0, "flips": [], "recent": []}


def test_signal_changes_reports_what_digest_recorded(client):
    """digest 가 남긴 이력을 리서치 화면이 읽는 경로."""
    from datetime import datetime, timedelta

    import app.database as database
    from app.models.signal_change import SignalChange

    session = database.SessionLocal()
    try:
        now = datetime.utcnow()
        session.add_all([
            SignalChange(ticker="005930", name="삼성전자", previous_signal="HOLD",
                         current_signal="BUY", direction="up", source="digest",
                         recorded_at=now - timedelta(days=1)),
            SignalChange(ticker="005930", name="삼성전자", previous_signal="BUY",
                         current_signal="HOLD", direction="down", source="digest",
                         recorded_at=now - timedelta(days=4)),
            SignalChange(ticker="000660", name="SK하이닉스", current_signal="SELL",
                         direction="down", source="digest",
                         recorded_at=now - timedelta(days=2)),
        ])
        session.commit()
    finally:
        session.close()

    body = client.get("/api/retrospective/signal-changes?days=30").json()

    assert body["total"] == 3
    # 두 번 이상 뒤집힌 종목만 flips 에 오른다.
    assert [f["ticker"] for f in body["flips"]] == ["005930"]
    assert body["flips"][0]["count"] == 2
    assert body["recent"][0]["ticker"] == "005930"


def test_signal_changes_can_narrow_to_one_ticker(client):
    """종목 분석 화면이 "이 신호, 원래 자주 뒤집히나"를 물을 때 쓰는 경로."""
    from datetime import datetime, timedelta

    import app.database as database
    from app.models.signal_change import SignalChange

    session = database.SessionLocal()
    try:
        now = datetime.utcnow()
        session.add_all([
            SignalChange(ticker="005930", name="삼성전자", current_signal="BUY",
                         direction="up", kind="signal", source="digest",
                         recorded_at=now - timedelta(days=1)),
            SignalChange(ticker="005930", name="삼성전자", current_signal="HOLD",
                         direction="down", kind="signal", source="digest",
                         recorded_at=now - timedelta(days=3)),
            SignalChange(ticker="000660", name="SK하이닉스", current_signal="SELL",
                         direction="down", kind="signal", source="digest",
                         recorded_at=now - timedelta(days=2)),
        ])
        session.commit()
    finally:
        session.close()

    body = client.get("/api/retrospective/signal-changes?ticker=005930").json()

    assert body["ticker"] == "005930"
    assert body["total"] == 2
    assert {row["ticker"] for row in body["recent"]} == {"005930"}


def test_signal_changes_rejects_an_out_of_range_window(client):
    assert client.get("/api/retrospective/signal-changes?days=0").status_code == 422
    assert client.get("/api/retrospective/signal-changes?days=999").status_code == 422


def test_analysis_records_a_buy_recommendation(client, forced_buy_signal):
    """/analysis 는 매수 신호일 때 추천을 남긴다. 그 쓰기가 테스트 DB 로 가는지 확인."""
    assert client.get("/api/retrospective/summary").json()["total"] == 0

    body = client.get("/api/stocks/005930/analysis").json()
    assert body["signal"]["signal"] == "BUY"

    summary = client.get("/api/retrospective/summary").json()
    assert summary["total"] == 1
    assert summary["open"] == 1
    assert summary["recent"][0]["ticker"] == "005930"
    assert summary["recent"][0]["signal"] == "BUY"


def test_analysis_does_not_record_the_same_ticker_twice(client, forced_buy_signal):
    # 24시간 중복 방지. 화면을 새로고침할 때마다 추천이 쌓이면 적중률이 오염된다.
    client.get("/api/stocks/005930/analysis")
    client.get("/api/stocks/005930/analysis")
    assert client.get("/api/retrospective/summary").json()["total"] == 1


def test_analysis_does_not_record_a_non_buy_signal(client):
    signal = client.get("/api/stocks/005930/analysis").json()["signal"]["signal"]
    assert signal not in {"STRONG BUY", "BUY", "WEAK BUY"}
    assert client.get("/api/retrospective/summary").json()["total"] == 0


# --- export_router --------------------------------------------------------


def test_export_stock_csv(client):
    response = client.get("/api/export/stock/005930.csv")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    assert "attachment" in response.headers["content-disposition"]
    assert response.text.startswith("﻿")  # 엑셀 한글용 BOM
    rows = _csv_rows(response)
    assert "close" in rows[0]
    assert len(rows) == ROWS_1Y + 1  # 헤더 + 1년치


def test_export_watchlist_csv(client):
    client.post("/api/watchlist", json={"ticker": "005930", "name": "삼성전자"})
    rows = _csv_rows(client.get("/api/export/watchlist.csv"))
    assert rows[0][0] == "ticker"
    assert rows[1][0] == "005930"
    assert rows[1][-1] == ""  # error 칸이 비어야 성공


def test_export_watchlist_csv_escapes_formula_injection(client):
    # 종목명은 외부 출처다. '='로 시작하면 엑셀이 수식으로 실행한다.
    client.post("/api/watchlist", json={"ticker": "005930", "name": "=HYPERLINK(\"http://evil\")"})
    rows = _csv_rows(client.get("/api/export/watchlist.csv"))
    assert rows[1][1].startswith("'=")


def test_export_buy_signals_csv(client):
    response = client.get("/api/export/buy-signals.csv?min_signal=WEAK_BUY")
    assert response.status_code == 200
    rows = _csv_rows(response)
    assert rows[0][:3] == ["rank", "ticker", "name"]
