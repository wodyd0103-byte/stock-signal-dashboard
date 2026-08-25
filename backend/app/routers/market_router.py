from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from typing import Any, Literal

from fastapi import APIRouter, Query

from app.core.config import get_settings
from app.services import scan_service
from app.services.analysis_service import (
    build_signal,
    data_provider,
    fundamental_dict,
    indicator_service,
    risk_service,
)
from app.services.scan_service import DISCLAIMER, now_kst

router = APIRouter(prefix="/market", tags=["market"])
settings = get_settings()


@router.get("/sentiment")
def get_market_sentiment(force_refresh: bool = Query(False)) -> dict[str, Any]:
    """시장 공포·탐욕 지수 (0=극도공포 ~ 100=극도탐욕)."""
    from app.services.market_sentiment_service import MarketSentimentService
    return MarketSentimentService().get(force_refresh=force_refresh).to_dict()


@router.get("/representative-stocks")
def get_representative_stocks(
    market: Literal["all", "KR", "US"] = Query("all"),
    kr_limit: int = Query(settings.BUY_SIGNAL_KR_LIMIT, ge=0, le=100),
    us_limit: int = Query(settings.BUY_SIGNAL_US_LIMIT, ge=0, le=100),
    source: Literal["auto", "fallback"] = Query("auto"),
) -> dict[str, Any]:
    return scan_service.representative_stocks_payload(
        market=market,
        kr_limit=kr_limit,
        us_limit=us_limit,
        source=source,
    )


@router.get("/buy-signals")
def get_buy_signals(
    market: Literal["all", "KR", "US"] = Query("all"),
    min_signal: Literal["WEAK_BUY", "BUY", "STRONG_BUY"] = Query("WEAK_BUY"),
    kr_limit: int = Query(settings.BUY_SIGNAL_KR_LIMIT, ge=0, le=100),
    us_limit: int = Query(settings.BUY_SIGNAL_US_LIMIT, ge=0, le=100),
    limit: int = Query(20, ge=1, le=200),
    include_sample: bool = Query(False),
    source: Literal["auto", "fallback"] = Query("auto"),
    sort_by: Literal["signal", "buy_score", "risk_score", "change_rate"] = Query("signal"),
    force_refresh: bool = Query(False),
) -> dict[str, Any]:
    return scan_service.buy_signals_payload(
        market=market,
        min_signal=min_signal,
        kr_limit=kr_limit,
        us_limit=us_limit,
        limit=limit,
        include_sample=include_sample,
        source=source,
        sort_by=sort_by,
        force_refresh=force_refresh,
    )


@router.get("/compare")
def compare_stocks(tickers: str = Query(..., description="쉼표 구분 2~4종목")) -> dict[str, Any]:
    """2~4종목 핵심 지표 횡단 비교 (가격·수익률·변동성·신호·밸류)."""
    seen: list[str] = []
    for raw in tickers.split(","):
        candidate = raw.strip()
        if not candidate:
            continue
        resolved = data_provider.resolve_ticker(candidate)
        if resolved not in seen:
            seen.append(resolved)
    if not (2 <= len(seen) <= 4):
        return {"error": "비교는 2~4개 종목이 필요합니다.", "items": []}

    with ThreadPoolExecutor(max_workers=len(seen)) as executor:
        items = list(executor.map(_compare_one, seen))
    return {"items": items, "disclaimer": DISCLAIMER, "updated_at": now_kst().isoformat()}


def _compare_one(ticker: str) -> dict[str, Any]:
    """단일 종목 비교용 경량 지표 (병렬 워커). 실패 시 error 필드."""
    try:
        result = data_provider.fetch_ohlcv(ticker, "1y")
        enriched = indicator_service.enrich(result.data)
        if enriched.empty:
            return {"ticker": ticker, "error": "데이터 없음"}
        close = enriched["close"].astype(float)
        current = float(close.iloc[-1])
        prev = float(close.iloc[-2]) if len(close) >= 2 else current
        change_rate = (current - prev) / prev * 100 if prev else 0.0

        def _ret(n: int):
            if len(close) <= n:
                return None
            base = float(close.iloc[-1 - n])
            return round((current / base - 1) * 100, 2) if base else None

        daily = close.pct_change().dropna()
        vol = round(float(daily.tail(60).std()) * (252 ** 0.5) * 100, 1) if len(daily) >= 20 else None

        risk = risk_service.analyze(result.ticker, "1y", enriched)
        fundamental = fundamental_dict(result.ticker) if result.market == "KR" else None
        sig = build_signal(result, "1y", enriched, risk.risk_score, fundamental=fundamental)

        return {
            "ticker": result.ticker,
            "market": result.market,
            "current_price": round(current, 2),
            "change_rate": round(change_rate, 2),
            "return_20d": _ret(20),
            "return_60d": _ret(60),
            "volatility": vol,
            "signal": sig.signal,
            "buy_score": sig.buy_score,
            "risk_score": sig.risk_score,
            "per": (fundamental or {}).get("per"),
            "pbr": (fundamental or {}).get("pbr"),
        }
    except Exception as exc:
        return {"ticker": ticker, "error": str(exc)}
