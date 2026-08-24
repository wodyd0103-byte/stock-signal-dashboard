from __future__ import annotations

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
from app.services import analysis_service
from app.services.analysis_service import AnalysisError
from app.services.backtest_service import BacktestService
from app.services.data_provider import DataProviderError, PriceDataResult
from app.services.retrospective_service import RetrospectiveService


DISCLAIMER = "본 서비스의 분석, 예측, 매수/매도 신호는 과거 데이터와 알고리즘을 기반으로 한 참고 정보입니다. 실제 투자 결과를 보장하지 않으며, 모든 투자 판단과 책임은 사용자 본인에게 있습니다."

router = APIRouter(prefix="/stocks", tags=["stocks"])
debug_router = APIRouter(prefix="/debug", tags=["debug"])

backtest_service = BacktestService()
_retro_service = RetrospectiveService()

# 분석 파이프라인은 app/services/analysis_service.py로 옮겼다.
# 다른 라우터와 scheduler_service가 아래 이름들을 stock_router에서 import하고 있어
# 호출부를 옮길 때까지 별칭으로 유지한다.
data_provider = analysis_service.data_provider
indicator_service = analysis_service.indicator_service
risk_service = analysis_service.risk_service
prediction_service = analysis_service.prediction_service
signal_service = analysis_service.signal_service
ml_signal_service = analysis_service.ml_signal_service
regime_service = analysis_service.regime_service
korean_market_service = analysis_service.korean_market_service
_sector_service = analysis_service._sector_service
_ic_service = analysis_service._ic_service
_learned_service = analysis_service._learned_service

_quote_from_frame = analysis_service.quote_from_frame
_build_signal = analysis_service.build_signal
_market_sentiment_dict = analysis_service.market_sentiment_dict
_supply_demand_dict = analysis_service.supply_demand_dict
_news_sentiment_dict = analysis_service.news_sentiment_dict
_sector_dict = analysis_service.sector_dict
_disclosure_dict = analysis_service.disclosure_dict
_fundamental_dict = analysis_service.fundamental_dict
_return_pct = analysis_service.return_pct
_liquidity_score = analysis_service.liquidity_score


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
    bundle = _analyze(ticker, period)
    quote = bundle.quote
    signal = bundle.signal

    # 회고: 매수 신호면 추천 기록 (24h 중복 방지)
    try:
        _retro_service.record(
            db, ticker=bundle.result.ticker, name=None, market=bundle.result.market,
            signal=signal.signal, buy_score=signal.buy_score, risk_score=signal.risk_score,
            price=quote["current_price"], horizon_days=5,
        )
    except Exception:
        pass

    return AnalysisResponse(
        ticker=bundle.result.ticker,
        period=period,
        current_price=quote["current_price"],
        previous_close=quote["previous_close"],
        change=quote["change"],
        change_rate=quote["change_rate"],
        volume=quote["volume"],
        signal=signal,
        indicators=bundle.indicators,
        risk=bundle.risk,
        predictions=bundle.prediction.predictions,
        long_term_predictions=bundle.prediction.long_term_predictions,
        optimal_exit=bundle.prediction.optimal_exit,
        price_target=bundle.prediction.price_target,
        market_sentiment=bundle.market_sentiment,
        supply_demand=bundle.supply_demand,
        news_sentiment=bundle.news_sentiment,
        sector=bundle.sector,
        disclosure=bundle.disclosure,
        learned_signal=bundle.learned_signal,
        fundamental=bundle.fundamental,
        price_history=_price_points(bundle.enriched),
        levels=bundle.levels,
        disclaimer=DISCLAIMER,
        last_updated=datetime.utcnow(),
        **bundle.result.metadata(),
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


def _http_error(exc: Exception, ticker: str) -> HTTPException:
    """서비스 레이어의 도메인 예외를 HTTP 응답으로 변환한다."""
    if isinstance(exc, DataProviderError):
        status_code = 400 if exc.error_type == "invalid_ticker_format" else 502
        return HTTPException(status_code=status_code, detail=exc.to_payload(ticker))
    return HTTPException(status_code=500, detail=str(exc))


def _load_price_data_result(ticker: str, period: str) -> PriceDataResult:
    try:
        return analysis_service.load_price_data_result(ticker, period)
    except DataProviderError as exc:
        raise _http_error(exc, ticker) from exc


def _load_enriched(ticker: str, period: str) -> tuple[PriceDataResult, pd.DataFrame]:
    try:
        return analysis_service.load_enriched(ticker, period)
    except (DataProviderError, AnalysisError) as exc:
        raise _http_error(exc, ticker) from exc


def _analyze(ticker: str, period: str) -> analysis_service.AnalysisBundle:
    try:
        return analysis_service.analyze(ticker, period)
    except (DataProviderError, AnalysisError) as exc:
        raise _http_error(exc, ticker) from exc


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
