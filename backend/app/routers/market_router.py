from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, wait
from datetime import datetime, timedelta, timezone
from threading import Lock
from typing import Any, Literal

from fastapi import APIRouter, Query

from app.core.config import get_settings
from app.services.data_provider import DataProviderError, StockDataProvider
from app.services.indicator_service import IndicatorService
from app.services.korean_market_service import KoreanMarketService
from app.services.ml_signal_service import MLSignalService
from app.services.prediction_service import PredictionService
from app.services.ranking_service import RankingService
from app.services.regime_service import RegimeService
from app.services.risk_service import RiskService
from app.services.signal_service import SignalService
from app.services.universe_service import UniverseService


router = APIRouter(prefix="/market", tags=["market"])
settings = get_settings()
data_provider = StockDataProvider()
indicator_service = IndicatorService()
risk_service = RiskService()
prediction_service = PredictionService()
signal_service = SignalService()
universe_service = UniverseService()
ranking_service = RankingService()
regime_service = RegimeService()
ml_signal_service = MLSignalService()
korean_market_service = KoreanMarketService()

_analysis_cache: dict[tuple[str, str, bool], tuple[datetime, dict[str, Any]]] = {}
_analysis_cache_lock = Lock()

SIGNAL_ORDER = {
    "STRONG BUY": 0,
    "BUY": 1,
    "WEAK BUY": 2,
    "HOLD": 3,
    "WEAK SELL": 4,
    "SELL": 5,
    "STRONG SELL": 6,
}
MIN_SIGNAL_ALLOWED = {
    "WEAK_BUY": {"STRONG BUY", "BUY", "WEAK BUY"},
    "BUY": {"STRONG BUY", "BUY"},
    "STRONG_BUY": {"STRONG BUY"},
}
DISCLAIMER = "본 결과는 과거 데이터와 알고리즘 기반 참고 정보이며 투자 수익을 보장하지 않습니다."


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
    result = universe_service.get_representative_stocks(
        market=market,
        kr_limit=kr_limit,
        us_limit=us_limit,
        source=source,
    )
    return {
        "market": result.market,
        "kr_count": result.kr_count,
        "us_count": result.us_count,
        "total_count": len(result.items),
        "source": result.source,
        "items": result.items,
        "updated_at": result.updated_at.isoformat(),
    }


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
    return _buy_signals_payload(
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


_payload_cache: dict[tuple, tuple[datetime, dict[str, Any]]] = {}
_payload_cache_lock = Lock()
_PAYLOAD_TTL = 600  # 10분 — 발굴 레일 사전계산 유지


def _buy_signals_payload(
    market: str = "all",
    min_signal: str = "WEAK_BUY",
    kr_limit: int = 100,
    us_limit: int = 100,
    limit: int = 20,
    include_sample: bool = False,
    source: str = "auto",
    sort_by: str = "signal",
    force_refresh: bool = False,
) -> dict[str, Any]:
    """다른 라우터(export 등)에서 재사용 가능한 순수 함수. 10분 payload 캐시."""
    pkey = (market, min_signal, kr_limit, us_limit, limit, include_sample, source, sort_by)
    if not force_refresh:
        with _payload_cache_lock:
            cached = _payload_cache.get(pkey)
        if cached and (datetime.utcnow() - cached[0]).total_seconds() < _PAYLOAD_TTL:
            return cached[1]

    universe = universe_service.get_representative_stocks(
        market=market,
        kr_limit=kr_limit,
        us_limit=us_limit,
        source=source,
        force_refresh=force_refresh,
    )
    successes: list[dict[str, Any]] = []
    failed_items: list[dict[str, Any]] = []

    batch_size = max(1, min(settings.BUY_SIGNAL_BATCH_SIZE, 50))
    max_workers = max(1, min(settings.BUY_SIGNAL_MAX_WORKERS, batch_size, len(universe.items) or 1))

    for batch in _batched(universe.items, batch_size):
        batch_workers = max(1, min(max_workers, len(batch)))
        batch_timeout = max(
            settings.BUY_SIGNAL_ITEM_TIMEOUT_SECONDS,
            settings.BUY_SIGNAL_ITEM_TIMEOUT_SECONDS * ((len(batch) + batch_workers - 1) // batch_workers),
        )
        executor = ThreadPoolExecutor(max_workers=batch_workers)
        futures = {
            executor.submit(_analyze_representative_stock, stock, force_refresh): stock
            for stock in batch
        }
        done, not_done = wait(futures.keys(), timeout=batch_timeout)

        for future in done:
            stock = futures[future]
            try:
                successes.append(future.result())
            except Exception as exc:
                failed_items.append(_failed_item(stock, str(exc)))

        for future in not_done:
            stock = futures[future]
            future.cancel()
            failed_items.append(
                _failed_item(
                    stock,
                    f"분석 제한 시간({batch_timeout}초)을 초과했습니다. 데이터 제공자 응답 지연 또는 네트워크 문제일 수 있습니다.",
                )
            )
        executor.shutdown(wait=False, cancel_futures=True)

    regime = regime_service.analyze_universe(successes, market).to_dict()
    ranked_successes = ranking_service.rank_universe_signals(successes)
    ranked_successes = [
        signal_service.apply_ranked_signal(item, str(regime["market_regime"]))
        for item in ranked_successes
    ]

    allowed_signals = MIN_SIGNAL_ALLOWED[min_signal]
    matched = [
        item
        for item in ranked_successes
        if item["signal"] in allowed_signals and (include_sample or not item["is_sample"])
    ]
    matched.sort(key=lambda item: _sort_key(item, sort_by))
    ranked = [{**item, "rank": index + 1} for index, item in enumerate(matched)]
    limited_items = ranked[:limit]

    payload = {
        "updated_at": _now_kst().isoformat(),
        "refresh_seconds": settings.BUY_SIGNAL_REFRESH_SECONDS,
        "market": market,
        "market_regime": regime["market_regime"],
        "regime_score": regime["regime_score"],
        "regime_description": regime["description"],
        "source": universe.source,
        "kr_checked": universe.kr_count,
        "us_checked": universe.us_count,
        "total_checked": len(universe.items),
        "total_success": len(ranked_successes),
        "total_failed": len(failed_items),
        "total_matched": len(matched),
        "strong_buy_count": len([item for item in matched if item["signal"] == "STRONG BUY"]),
        "buy_count": len([item for item in matched if item["signal"] == "BUY"]),
        "weak_buy_count": len([item for item in matched if item["signal"] == "WEAK BUY"]),
        "items": limited_items,
        "failed_items": failed_items,
        "disclaimer": DISCLAIMER,
    }
    with _payload_cache_lock:
        _payload_cache[pkey] = (datetime.utcnow(), payload)
    return payload


def _analyze_representative_stock(stock: dict[str, str], force_refresh: bool = False) -> dict[str, Any]:
    cache_key = (stock["ticker"], "1y", settings.ALLOW_SAMPLE_FALLBACK)
    now = datetime.utcnow()

    if not force_refresh:
        with _analysis_cache_lock:
            cached = _analysis_cache.get(cache_key)
        if cached and now - cached[0] < timedelta(seconds=settings.DATA_CACHE_TTL_SECONDS):
            return dict(cached[1])

    try:
        result = data_provider.fetch_ohlcv(stock["ticker"], "1y", force_refresh=force_refresh)
    except DataProviderError as exc:
        raise RuntimeError(exc.message) from exc

    enriched = indicator_service.enrich(result.data)
    if enriched.empty or len(enriched) < 2:
        raise RuntimeError("지표 계산에 필요한 가격 데이터가 부족합니다.")

    latest = enriched.iloc[-1]
    previous = enriched.iloc[-2]
    previous_close = float(previous["close"]) if float(previous["close"]) else float(latest["close"])
    change_rate = (float(latest["close"]) - previous_close) / previous_close * 100 if previous_close else 0.0
    risk = risk_service.analyze(result.ticker, "1y", enriched)
    return_5d = _return_pct(enriched, 5)
    return_20d = _return_pct(enriched, 20)
    volatility_20d = _volatility(enriched)
    volume_value_20d = _volume_value_20d(enriched)
    liquidity_score = _liquidity_score(enriched)
    ml_signal = ml_signal_service.predict_up_probability(enriched, return_20d).to_dict()
    korean_context = None
    if result.market == "KR":
        korean_context = korean_market_service.analyze(result.ticker, enriched, fetch_external=False).to_dict()
    signal = signal_service.score(
        enriched,
        risk.risk_score,
        prediction=None,
        ml_signal=ml_signal,
        regime={"market_regime": "SIDEWAYS", "regime_score": 0, "adjustments": []},
        korean_market=korean_context,
        relative_strength_score=return_20d,
        liquidity_score=liquidity_score,
        signal_source="raw_score_before_rank",
    )
    item = {
        "name": stock["name"],
        "ticker": result.ticker,
        "market": result.market,
        "current_price": round(float(latest["close"]), 2),
        "change_rate": round(change_rate, 2),
        "signal": signal.signal,
        "buy_score": signal.buy_score,
        "sell_score": signal.sell_score,
        "risk_score": signal.risk_score,
        "raw_buy_score": signal.raw_buy_score,
        "raw_sell_score": signal.raw_sell_score,
        "final_buy_score": signal.final_buy_score,
        "final_sell_score": signal.final_sell_score,
        "relative_strength_score": signal.relative_strength_score,
        "liquidity_score": signal.liquidity_score,
        "regime_score": signal.regime_score,
        "ml_up_probability": signal.ml_up_probability,
        "ml_signal": signal.ml_signal,
        "model_confidence": signal.model_confidence,
        "return_5d": return_5d,
        "return_20d": return_20d,
        "volatility_20d": volatility_20d,
        "volume_value_20d": volume_value_20d,
        "buy_score_zone": signal.buy_score_zone,
        "sell_score_zone": signal.sell_score_zone,
        "risk_score_zone": signal.risk_score_zone,
        "buy_score_percentile": signal.buy_score_percentile,
        "sell_score_percentile": signal.sell_score_percentile,
        "relative_strength_rank": signal.relative_strength_rank,
        "liquidity_rank": signal.liquidity_rank,
        "risk_rank": signal.risk_rank,
        "score_zone": signal.buy_score_zone,
        "signal_description": signal.signal_description,
        "reasons": signal.reasons[:3],
        "hold_reasons": signal.hold_reasons,
        "score_adjustments": signal.score_adjustments,
        "market_regime": signal.market_regime,
        "signal_source": signal.signal_source,
        "source": result.source,
        "is_sample": result.is_sample,
        "provider_status": result.provider_status,
        "provider_message": result.provider_message,
        "provider_error": result.provider_error,
        "last_analyzed_at": _now_kst().isoformat(),
    }
    with _analysis_cache_lock:
        _analysis_cache[cache_key] = (now, dict(item))
    return item


def _sort_key(item: dict[str, Any], sort_by: str) -> tuple[Any, ...]:
    signal_rank = SIGNAL_ORDER.get(item["signal"], 99)
    buy_score = int(item.get("buy_score", 0))
    final_buy_score = int(item.get("final_buy_score", buy_score))
    risk_score = int(item.get("risk_score", 100))
    change_rate = float(item.get("change_rate", 0))
    buy_percentile = float(item.get("buy_score_percentile") or 0)
    liquidity_score = float(item.get("liquidity_score") or 0)
    if sort_by == "buy_score":
        return (-buy_percentile, -final_buy_score, signal_rank, risk_score, -liquidity_score)
    if sort_by == "risk_score":
        return (risk_score, signal_rank, -buy_percentile, -final_buy_score, -liquidity_score)
    if sort_by == "change_rate":
        return (-change_rate, signal_rank, -buy_percentile, -final_buy_score, risk_score)
    return (signal_rank, -buy_percentile, -final_buy_score, risk_score, -liquidity_score)


def _failed_item(stock: dict[str, str], message: str) -> dict[str, str]:
    return {
        "name": stock["name"],
        "ticker": stock["ticker"],
        "market": stock["market"],
        "error": message,
        "provider_error": message,
    }


def _batched(items: list[dict[str, str]], size: int) -> list[list[dict[str, str]]]:
    return [items[index : index + size] for index in range(0, len(items), size)]


def _return_pct(enriched, days: int) -> float:
    if len(enriched) <= days:
        return 0.0
    base = float(enriched.iloc[-days - 1]["close"])
    if base == 0:
        return 0.0
    return round((float(enriched.iloc[-1]["close"]) / base - 1) * 100, 2)


def _volatility(enriched) -> float:
    returns = enriched["close"].pct_change().dropna() * 100
    return round(float(returns.tail(20).std()) if len(returns) >= 2 else 0.0, 2)


def _volume_value_20d(enriched) -> float:
    value = enriched["close"] * enriched["volume"]
    return round(float(value.tail(20).mean()) if len(value) else 0.0, 2)


def _liquidity_score(enriched) -> float:
    value = enriched["close"] * enriched["volume"]
    latest = float(value.iloc[-1]) if len(value) else 0.0
    average = float(value.tail(20).mean()) if len(value) else latest
    ratio = latest / average if average else 1.0
    return round(max(0, min(100, 45 + ratio * 25)), 2)


def _now_kst() -> datetime:
    return datetime.now(timezone(timedelta(hours=9)))


def _compare_one(ticker: str) -> dict[str, Any]:
    """단일 종목 비교용 경량 지표 (병렬 워커). 실패 시 error 필드."""
    from app.services.analysis_service import build_signal, fundamental_dict
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


@router.get("/compare")
def compare_stocks(tickers: str = Query(..., description="쉼표 구분 2~4종목")) -> dict[str, Any]:
    """2~4종목 핵심 지표 횡단 비교 (가격·수익률·변동성·신호·밸류)."""
    seen: list[str] = []
    for t in tickers.split(","):
        t = t.strip()
        if not t:
            continue
        rt = data_provider.resolve_ticker(t)
        if rt not in seen:
            seen.append(rt)
    if not (2 <= len(seen) <= 4):
        return {"error": "비교는 2~4개 종목이 필요합니다.", "items": []}

    with ThreadPoolExecutor(max_workers=len(seen)) as ex:
        items = list(ex.map(_compare_one, seen))
    return {"items": items, "disclaimer": DISCLAIMER, "updated_at": _now_kst().isoformat()}
