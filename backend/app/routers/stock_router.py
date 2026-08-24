from __future__ import annotations

from datetime import datetime
from typing import Any

import numpy as np
import pandas as pd
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.routers.analysis_http import analyze as _analyze, load_enriched as _load_enriched
from app.schemas.analysis import AnalysisResponse, IndicatorResponse, SignalResponse
from app.schemas.backtest import BacktestResponse
from app.schemas.prediction import PredictionResponse
from app.schemas.stock import Period, PricePoint, PriceResponse
from app.services.analysis_service import (
    build_signal,
    data_provider,
    indicator_service,
    prediction_service,
    quote_from_frame,
    risk_service,
)
from app.services.backtest_service import BacktestService
from app.services.retrospective_service import RetrospectiveService


DISCLAIMER = "본 서비스의 분석, 예측, 매수/매도 신호는 과거 데이터와 알고리즘을 기반으로 한 참고 정보입니다. 실제 투자 결과를 보장하지 않으며, 모든 투자 판단과 책임은 사용자 본인에게 있습니다."

router = APIRouter(prefix="/stocks", tags=["stocks"])
debug_router = APIRouter(prefix="/debug", tags=["debug"])

backtest_service = BacktestService()
_retro_service = RetrospectiveService()


@router.get("/{ticker}/price", response_model=PriceResponse)
def get_price(ticker: str, period: Period = Query("1y")) -> PriceResponse:
    result, enriched = _load_enriched(ticker, period)
    quote = quote_from_frame(result, period, enriched)
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
    signal = build_signal(result, period, enriched, risk.risk_score)
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
