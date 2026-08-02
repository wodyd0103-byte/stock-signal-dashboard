from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from typing import Any

import numpy as np
import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.analysis import AnalysisResponse, IndicatorResponse, SignalResponse
from app.schemas.backtest import BacktestResponse
from app.schemas.prediction import PredictionResponse
from app.schemas.stock import Period, PricePoint, PriceResponse
from app.services.backtest_service import BacktestService
from app.services.data_provider import DataProviderError, PriceDataResult, StockDataProvider
from app.services.indicator_service import IndicatorService
from app.services.korean_market_service import KoreanMarketService
from app.services.ml_signal_service import MLSignalService
from app.services.prediction_service import PredictionService
from app.services.regime_service import RegimeService
from app.services.risk_service import RiskService
from app.services.signal_service import SignalService


DISCLAIMER = "본 서비스의 분석, 예측, 매수/매도 신호는 과거 데이터와 알고리즘을 기반으로 한 참고 정보입니다. 실제 투자 결과를 보장하지 않으며, 모든 투자 판단과 책임은 사용자 본인에게 있습니다."

router = APIRouter(prefix="/stocks", tags=["stocks"])
debug_router = APIRouter(prefix="/debug", tags=["debug"])
data_provider = StockDataProvider()
indicator_service = IndicatorService()
risk_service = RiskService()
prediction_service = PredictionService()
signal_service = SignalService()
backtest_service = BacktestService()
ml_signal_service = MLSignalService()
regime_service = RegimeService()
korean_market_service = KoreanMarketService()

from app.services.retrospective_service import RetrospectiveService
_retro_service = RetrospectiveService()

from app.services.sector_service import SectorService
_sector_service = SectorService(data_provider)

from app.services.ic_service import ICService
from app.services.universe_service import UniverseService as _Uni
from app.services.learned_signal_service import LearnedSignalService
_ic_service = ICService(data_provider, indicator_service, _Uni())
_learned_service = LearnedSignalService(_ic_service)


@router.get("/{ticker}/price", response_model=PriceResponse)
def get_price(ticker: str, period: Period = Query("1y")) -> PriceResponse:
    result, enriched = _load_enriched(ticker, period)
    quote = _quote_from_frame(result, period, enriched)
    points = _price_points(enriched)
    return PriceResponse(**quote, data=points, prices=points)


@router.get("/{ticker}/indicators", response_model=IndicatorResponse)
def get_indicators(ticker: str, period: Period = Query("1y")) -> IndicatorResponse:
    result, enriched = _load_enriched(ticker, period)
    indicators, levels = indicator_service.summarize(enriched)
    return IndicatorResponse(
        ticker=result.ticker,
        period=period,
        indicators=indicators,
        levels=levels,
        last_updated=datetime.utcnow(),
        **result.metadata(),
    )


@router.get("/{ticker}/prediction", response_model=PredictionResponse)
def get_prediction(ticker: str, period: Period = Query("1y")) -> PredictionResponse:
    result, enriched = _load_enriched(ticker, period)
    prediction = prediction_service.predict(result.ticker, period, enriched)
    return prediction.model_copy(update=result.metadata())


@router.get("/{ticker}/signal", response_model=SignalResponse)
def get_signal(ticker: str, period: Period = Query("1y")) -> SignalResponse:
    result, enriched = _load_enriched(ticker, period)
    risk = risk_service.analyze(result.ticker, period, enriched)
    signal = _build_signal(result, period, enriched, risk.risk_score)
    return SignalResponse(ticker=result.ticker, period=period, **signal.model_dump(), **result.metadata())


@router.get("/{ticker}/analysis", response_model=AnalysisResponse)
def get_analysis(ticker: str, period: Period = Query("1y"), db: Session = Depends(get_db)) -> AnalysisResponse:
    result, enriched = _load_enriched(ticker, period)
    quote = _quote_from_frame(result, period, enriched)
    indicators, levels = indicator_service.summarize(enriched)
    risk = risk_service.analyze(result.ticker, period, enriched)
    prediction = prediction_service.predict(result.ticker, period, enriched)

    # 외부 fetch + 학습신호 병렬화 (콜드캐시 지연 누적 방지)
    def _learned():
        try:
            ls = _learned_service.score(enriched)
            return ls.to_dict() if ls else None
        except Exception:
            return None

    with ThreadPoolExecutor(max_workers=7) as ex:
        f_sentiment = ex.submit(_market_sentiment_dict)
        f_supply = ex.submit(_supply_demand_dict, result.ticker)
        f_news = ex.submit(_news_sentiment_dict, result.ticker)
        f_sector = ex.submit(_sector_dict, result.ticker)
        f_disc = ex.submit(_disclosure_dict, result.ticker)
        f_fund = ex.submit(_fundamental_dict, result.ticker)
        f_learned = ex.submit(_learned)
        sentiment = f_sentiment.result()
        supply_demand = f_supply.result()
        news = f_news.result()
        sector = f_sector.result()
        disclosure = f_disc.result()
        fundamental = f_fund.result()
        learned = f_learned.result()

    signal = _build_signal(
        result, period, enriched, risk.risk_score,
        market_sentiment=sentiment, news_sentiment=news, supply_demand=supply_demand,
        sector=sector, fundamental=fundamental,
    )

    # 회고: 매수 신호면 추천 기록 (24h 중복 방지)
    try:
        _retro_service.record(
            db, ticker=result.ticker, name=None, market=result.market,
            signal=signal.signal, buy_score=signal.buy_score, risk_score=signal.risk_score,
            price=quote["current_price"], horizon_days=5,
        )
    except Exception:
        pass

    return AnalysisResponse(
        ticker=result.ticker,
        period=period,
        current_price=quote["current_price"],
        previous_close=quote["previous_close"],
        change=quote["change"],
        change_rate=quote["change_rate"],
        volume=quote["volume"],
        signal=signal,
        indicators=indicators,
        risk=risk,
        predictions=prediction.predictions,
        long_term_predictions=prediction.long_term_predictions,
        optimal_exit=prediction.optimal_exit,
        price_target=prediction.price_target,
        market_sentiment=sentiment,
        supply_demand=supply_demand,
        news_sentiment=news,
        sector=sector,
        disclosure=disclosure,
        learned_signal=learned,
        fundamental=fundamental,
        price_history=_price_points(enriched),
        levels=levels,
        disclaimer=DISCLAIMER,
        last_updated=datetime.utcnow(),
        **result.metadata(),
    )


@router.get("/{ticker}/backtest", response_model=BacktestResponse)
def get_backtest(
    ticker: str,
    period: Period = Query("1y"),
    initial_capital: float = Query(10_000_000, ge=100_000),
    strategy: str = Query("regime_adjusted_strategy"),
) -> BacktestResponse:
    result, enriched = _load_enriched(ticker, period)
    backtest = backtest_service.run(result.ticker, period, enriched, initial_capital, strategy=strategy)
    return backtest.model_copy(update=result.metadata())


@debug_router.get("/data-provider/{ticker}")
def debug_data_provider(ticker: str, period: Period = Query("1y")) -> dict[str, Any]:
    return data_provider.debug_fetch(ticker, period)


def _load_enriched(ticker: str, period: str) -> tuple[PriceDataResult, pd.DataFrame]:
    result = _load_price_data_result(ticker, period)
    try:
        enriched = indicator_service.enrich(result.data)
        if enriched.empty:
            raise ValueError("지표 계산 후 가격 데이터가 비어 있습니다.")
        return result, enriched
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"데이터 처리 중 오류가 발생했습니다: {exc}") from exc


def _load_price_data_result(ticker: str, period: str) -> PriceDataResult:
    try:
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
    except DataProviderError as exc:
        status_code = 400 if exc.error_type == "invalid_ticker_format" else 502
        raise HTTPException(status_code=status_code, detail=exc.to_payload(ticker)) from exc


def _quote_from_frame(result: PriceDataResult, period: str, enriched: pd.DataFrame) -> dict[str, Any]:
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


def _build_signal(result: PriceDataResult, period: str, enriched: pd.DataFrame, risk_score: int, market_sentiment: dict | None = None, news_sentiment: dict | None = None, supply_demand: dict | None = None, sector: dict | None = None, fundamental: dict | None = None):
    regime = regime_service.analyze_from_frame(enriched).to_dict()
    relative_strength = _return_pct(enriched, 20)
    liquidity_score = _liquidity_score(enriched)
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
        liquidity_score=liquidity_score,
        market_sentiment=market_sentiment,
        news_sentiment=news_sentiment,
        sector=sector,
        fundamental=fundamental,
        signal_source="absolute_regime_ml",
    )


def _market_sentiment_dict() -> dict | None:
    """시장 공포·탐욕 지수 (캐시됨). 실패 시 None."""
    try:
        from app.services.market_sentiment_service import MarketSentimentService
        return MarketSentimentService().get().to_dict()
    except Exception:
        return None


def _supply_demand_dict(ticker: str) -> dict | None:
    """외국인/기관 수급 (네이버, 캐시됨). 국내 종목만. 실패 시 None."""
    try:
        from app.services.supply_demand_service import SupplyDemandService
        sd = SupplyDemandService().get(ticker)
        return sd.to_dict() if sd else None
    except Exception:
        return None


def _news_sentiment_dict(ticker: str) -> dict | None:
    """뉴스 감성 (네이버, 캐시됨). 국내 종목만. 실패 시 None."""
    try:
        from app.services.news_sentiment_service import NewsSentimentService
        ns = NewsSentimentService().get(ticker)
        return ns.to_dict() if ns else None
    except Exception:
        return None


def _sector_dict(ticker: str) -> dict | None:
    """업종 상대강도 (네이버 peer + OHLCV, 캐시됨). 국내 종목만. 실패 시 None."""
    try:
        s = _sector_service.get(ticker)
        return s.to_dict() if s else None
    except Exception:
        return None


def _disclosure_dict(ticker: str) -> dict | None:
    """공시 (네이버, 캐시됨). 국내 종목만. 실패 시 None."""
    try:
        from app.services.disclosure_service import DisclosureService
        d = DisclosureService().get(ticker)
        return d.to_dict() if d else None
    except Exception:
        return None


def _fundamental_dict(ticker: str) -> dict | None:
    """재무/펀더멘털 (네이버, 캐시됨). 국내 종목만. 실패 시 None."""
    try:
        from app.services.fundamental_service import FundamentalService
        f = FundamentalService().get(ticker)
        return f.to_dict() if f else None
    except Exception:
        return None


def _return_pct(enriched: pd.DataFrame, days: int) -> float:
    if len(enriched) <= days:
        return 0.0
    base = float(enriched.iloc[-days - 1]["close"])
    if base == 0:
        return 0.0
    return round((float(enriched.iloc[-1]["close"]) / base - 1) * 100, 2)


def _liquidity_score(enriched: pd.DataFrame) -> float:
    if enriched.empty:
        return 0.0
    value = enriched["close"] * enriched["volume"]
    latest = float(value.iloc[-1])
    average = float(value.tail(20).mean()) if len(value) else latest
    ratio = latest / average if average else 1.0
    return round(max(0, min(100, 45 + ratio * 25)), 2)


def _price_points(enriched: pd.DataFrame) -> list[PricePoint]:
    points: list[PricePoint] = []
    for _, row in enriched.iterrows():
        points.append(
            PricePoint(
                date=row["date"],
                open=round(float(row["open"]), 2),
                high=round(float(row["high"]), 2),
                low=round(float(row["low"]), 2),
                close=round(float(row["close"]), 2),
                volume=int(row["volume"]),
                ma5=_optional_float(row.get("ma5")),
                ma20=_optional_float(row.get("ma20")),
                ma60=_optional_float(row.get("ma60")),
                ma120=_optional_float(row.get("ma120")),
                rsi=_optional_float(row.get("rsi")),
                macd=_optional_float(row.get("macd")),
                macd_signal=_optional_float(row.get("macd_signal")),
                bollinger_upper=_optional_float(row.get("bollinger_upper")),
                bollinger_lower=_optional_float(row.get("bollinger_lower")),
            )
        )
    return points


def _optional_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        if np.isnan(value):
            return None
    except TypeError:
        return None
    return round(float(value), 4)
