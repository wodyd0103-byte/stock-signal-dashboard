"""종목 분석 조합 레이어.

가격 로딩 → 지표 → 리스크/예측 → 외부 컨텍스트(수급·뉴스·업종·공시·재무) → 신호까지를
HTTP와 무관하게 수행한다. 원래 `app/routers/stock_router.py`에 있던 헬퍼들이며,
라우터 외에도 export/watchlist/portfolio/market 라우터와 scheduler_service가 함께 쓰고 있어
서비스 레이어로 옮겼다.

이 모듈은 fastapi를 import하지 않는다. 실패는 도메인 예외(`DataProviderError`,
`AnalysisError`)로 올리고, HTTP 상태코드 변환은 라우터가 담당한다.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime
from typing import Any

import pandas as pd

from app.services.data_provider import DataProviderError, PriceDataResult, StockDataProvider
from app.services.ic_service import ICService
from app.services.indicator_service import IndicatorService
from app.services.korean_market_service import KoreanMarketService
from app.services.learned_signal_service import LearnedSignalService
from app.services.ml_signal_service import MLSignalService
from app.services.prediction_service import PredictionService
from app.services.regime_service import RegimeService
from app.services.risk_service import RiskService
from app.services.sector_service import SectorService
from app.services.signal_service import SignalService
from app.services.universe_service import UniverseService


class AnalysisError(Exception):
    """가격 데이터는 받았으나 지표 계산 이후 단계에서 실패한 경우."""


data_provider = StockDataProvider()
indicator_service = IndicatorService()
risk_service = RiskService()
prediction_service = PredictionService()
signal_service = SignalService()
ml_signal_service = MLSignalService()
regime_service = RegimeService()
korean_market_service = KoreanMarketService()

_sector_service = SectorService(data_provider)
_ic_service = ICService(data_provider, indicator_service, UniverseService())
_learned_service = LearnedSignalService(_ic_service)


@dataclass
class AnalysisBundle:
    """`analyze()` 한 번의 결과. 라우터는 응답 스키마로, CLI는 표/리포트로 변환한다."""

    result: PriceDataResult
    enriched: pd.DataFrame
    quote: dict[str, Any]
    indicators: Any
    levels: Any
    risk: Any
    prediction: Any
    signal: Any
    market_sentiment: dict | None
    supply_demand: dict | None
    news_sentiment: dict | None
    sector: dict | None
    disclosure: dict | None
    fundamental: dict | None
    learned_signal: dict | None


def load_price_data_result(ticker: str, period: str) -> PriceDataResult:
    result = data_provider.fetch_ohlcv(ticker, period)
    if result.data.empty:
        raise DataProviderError(
            "가격 데이터가 비어 있습니다.",
            ticker=result.ticker,
            market=result.market,
            selected_provider=result.selected_provider,
            source=result.source,
            error_type="empty_dataframe",
            providers_tried=result.providers_tried,
        )
    return result


def load_enriched(ticker: str, period: str) -> tuple[PriceDataResult, pd.DataFrame]:
    result = load_price_data_result(ticker, period)
    try:
        enriched = indicator_service.enrich(result.data)
        if enriched.empty:
            raise ValueError("지표 계산 후 가격 데이터가 비어 있습니다.")
        return result, enriched
    except Exception as exc:
        raise AnalysisError(f"데이터 처리 중 오류가 발생했습니다: {exc}") from exc


def quote_from_frame(result: PriceDataResult, period: str, enriched: pd.DataFrame) -> dict[str, Any]:
    latest = enriched.iloc[-1]
    previous = enriched.iloc[-2] if len(enriched) > 1 else latest
    previous_close = float(previous["close"]) if float(previous["close"]) else float(latest["close"])
    change = float(latest["close"] - previous["close"])
    return {
        "ticker": result.ticker,
        "period": period,
        "current_price": round(float(latest["close"]), 2),
        "previous_close": round(previous_close, 2),
        "change": round(change, 2),
        "change_rate": round(change / previous_close * 100 if previous_close else 0.0, 2),
        "volume": int(latest["volume"]),
        "last_updated": datetime.utcnow(),
        **result.metadata(),
    }


def build_signal(
    result: PriceDataResult,
    period: str,
    enriched: pd.DataFrame,
    risk_score: int,
    market_sentiment: dict | None = None,
    news_sentiment: dict | None = None,
    supply_demand: dict | None = None,
    sector: dict | None = None,
    fundamental: dict | None = None,
):
    regime = regime_service.analyze_from_frame(enriched).to_dict()
    relative_strength = return_pct(enriched, 20)
    liquidity = liquidity_score(enriched)
    ml_signal = ml_signal_service.predict_up_probability(enriched, relative_strength).to_dict()
    korean_context = None
    if result.market == "KR":
        korean_context = korean_market_service.analyze(result.ticker, enriched, fetch_external=False).to_dict()
        if supply_demand:
            # 수급 점수(0~100, 중립50)를 ±12 범위 가감으로 변환 → 매수 점수에 반영
            flow_adj = max(-12.0, min(12.0, (supply_demand["korean_flow_score"] - 50) / 50 * 12))
            korean_context = dict(korean_context or {})
            korean_context["korean_flow_score"] = flow_adj
            korean_context.setdefault("reasons", []).append(supply_demand["summary"])

    return signal_service.score(
        enriched,
        risk_score,
        prediction=None,
        ml_signal=ml_signal,
        regime=regime,
        korean_market=korean_context,
        relative_strength_score=relative_strength,
        liquidity_score=liquidity,
        market_sentiment=market_sentiment,
        news_sentiment=news_sentiment,
        sector=sector,
        fundamental=fundamental,
        signal_source="absolute_regime_ml",
    )


def market_sentiment_dict() -> dict | None:
    """시장 공포·탐욕 지수 (캐시됨). 실패 시 None."""
    try:
        from app.services.market_sentiment_service import MarketSentimentService
        return MarketSentimentService().get().to_dict()
    except Exception:
        return None


def supply_demand_dict(ticker: str) -> dict | None:
    """외국인/기관 수급 (네이버, 캐시됨). 국내 종목만. 실패 시 None."""
    try:
        from app.services.supply_demand_service import SupplyDemandService
        sd = SupplyDemandService().get(ticker)
        return sd.to_dict() if sd else None
    except Exception:
        return None


def news_sentiment_dict(ticker: str) -> dict | None:
    """뉴스 감성 (네이버, 캐시됨). 국내 종목만. 실패 시 None."""
    try:
        from app.services.news_sentiment_service import NewsSentimentService
        ns = NewsSentimentService().get(ticker)
        return ns.to_dict() if ns else None
    except Exception:
        return None


def sector_dict(ticker: str) -> dict | None:
    """업종 상대강도 (네이버 peer + OHLCV, 캐시됨). 국내 종목만. 실패 시 None."""
    try:
        s = _sector_service.get(ticker)
        return s.to_dict() if s else None
    except Exception:
        return None


def disclosure_dict(ticker: str) -> dict | None:
    """공시 (네이버, 캐시됨). 국내 종목만. 실패 시 None."""
    try:
        from app.services.disclosure_service import DisclosureService
        d = DisclosureService().get(ticker)
        return d.to_dict() if d else None
    except Exception:
        return None


def fundamental_dict(ticker: str) -> dict | None:
    """재무/펀더멘털 (네이버, 캐시됨). 국내 종목만. 실패 시 None."""
    try:
        from app.services.fundamental_service import FundamentalService
        f = FundamentalService().get(ticker)
        return f.to_dict() if f else None
    except Exception:
        return None


def learned_signal_dict(enriched: pd.DataFrame) -> dict | None:
    """IC 기반 학습 신호. 실패 시 None."""
    try:
        ls = _learned_service.score(enriched)
        return ls.to_dict() if ls else None
    except Exception:
        return None


def return_pct(enriched: pd.DataFrame, days: int) -> float:
    if len(enriched) <= days:
        return 0.0
    base = float(enriched.iloc[-days - 1]["close"])
    if base == 0:
        return 0.0
    return round((float(enriched.iloc[-1]["close"]) / base - 1) * 100, 2)


def liquidity_score(enriched: pd.DataFrame) -> float:
    if enriched.empty:
        return 0.0
    value = enriched["close"] * enriched["volume"]
    latest = float(value.iloc[-1])
    average = float(value.tail(20).mean()) if len(value) else latest
    ratio = latest / average if average else 1.0
    return round(max(0, min(100, 45 + ratio * 25)), 2)


def analyze(ticker: str, period: str = "1y") -> AnalysisBundle:
    """전체 분석 파이프라인. 외부 fetch는 병렬로 돌려 콜드캐시 지연 누적을 막는다."""
    result, enriched = load_enriched(ticker, period)
    quote = quote_from_frame(result, period, enriched)
    indicators, levels = indicator_service.summarize(enriched)
    risk = risk_service.analyze(result.ticker, period, enriched)
    prediction = prediction_service.predict(result.ticker, period, enriched)

    with ThreadPoolExecutor(max_workers=7) as ex:
        f_sentiment = ex.submit(market_sentiment_dict)
        f_supply = ex.submit(supply_demand_dict, result.ticker)
        f_news = ex.submit(news_sentiment_dict, result.ticker)
        f_sector = ex.submit(sector_dict, result.ticker)
        f_disc = ex.submit(disclosure_dict, result.ticker)
        f_fund = ex.submit(fundamental_dict, result.ticker)
        f_learned = ex.submit(learned_signal_dict, enriched)
        sentiment = f_sentiment.result()
        supply_demand = f_supply.result()
        news = f_news.result()
        sector = f_sector.result()
        disclosure = f_disc.result()
        fundamental = f_fund.result()
        learned = f_learned.result()

    signal = build_signal(
        result, period, enriched, risk.risk_score,
        market_sentiment=sentiment, news_sentiment=news, supply_demand=supply_demand,
        sector=sector, fundamental=fundamental,
    )

    return AnalysisBundle(
        result=result,
        enriched=enriched,
        quote=quote,
        indicators=indicators,
        levels=levels,
        risk=risk,
        prediction=prediction,
        signal=signal,
        market_sentiment=sentiment,
        supply_demand=supply_demand,
        news_sentiment=news,
        sector=sector,
        disclosure=disclosure,
        fundamental=fundamental,
        learned_signal=learned,
    )
