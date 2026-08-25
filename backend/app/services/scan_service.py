"""대표 종목 유니버스 일괄 스캔.

유니버스를 배치로 나눠 종목별 경량 분석을 돌리고, 상대순위를 매겨 매수 신호 목록을
만든다. 원래 `app/routers/market_router.py`에 있었으나 라우터 외에 export 라우터와
`scheduler_service`(캐시 워밍)가 함께 쓰고 있어 서비스 레이어로 옮겼다.

이 모듈은 fastapi를 import하지 않는다. 종목별 분석 싱글턴은
`analysis_service`의 것을 그대로 쓴다 — 같은 provider 인스턴스를 공유해야 캐시가
한 벌로 유지된다.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, wait
from datetime import datetime, timedelta, timezone
from threading import Lock
from typing import Any

from app.core.config import get_settings
from app.services.analysis_service import (
    data_provider,
    indicator_service,
    korean_market_service,
    liquidity_score,
    ml_signal_service,
    regime_service,
    return_pct,
    risk_service,
    signal_service,
)
from app.services.data_provider import DataProviderError
from app.services.ranking_service import RankingService
from app.services.universe_service import UniverseService

settings = get_settings()

universe_service = UniverseService()
ranking_service = RankingService()

_analysis_cache: dict[tuple[str, str, bool], tuple[datetime, dict[str, Any]]] = {}
_analysis_cache_lock = Lock()

_payload_cache: dict[tuple, tuple[datetime, dict[str, Any]]] = {}
_payload_cache_lock = Lock()
_PAYLOAD_TTL = 600  # 10분 — 발굴 레일 사전계산 유지

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


def now_kst() -> datetime:
    return datetime.now(timezone(timedelta(hours=9)))


def representative_stocks_payload(
    market: str = "all",
    kr_limit: int = 100,
    us_limit: int = 100,
    source: str = "auto",
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


def buy_signals_payload(
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
    """유니버스 스캔 결과. 10분 payload 캐시."""
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

    for batch in batched(universe.items, batch_size):
        batch_workers = max(1, min(max_workers, len(batch)))
        batch_timeout = max(
            settings.BUY_SIGNAL_ITEM_TIMEOUT_SECONDS,
            settings.BUY_SIGNAL_ITEM_TIMEOUT_SECONDS * ((len(batch) + batch_workers - 1) // batch_workers),
        )
        executor = ThreadPoolExecutor(max_workers=batch_workers)
        futures = {
            executor.submit(analyze_representative_stock, stock, force_refresh): stock
            for stock in batch
        }
        done, not_done = wait(futures.keys(), timeout=batch_timeout)

        for future in done:
            stock = futures[future]
            try:
                successes.append(future.result())
            except Exception as exc:
                failed_items.append(failed_item(stock, str(exc)))

        for future in not_done:
            stock = futures[future]
            future.cancel()
            failed_items.append(
                failed_item(
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
    matched.sort(key=lambda item: sort_key(item, sort_by))
    ranked = [{**item, "rank": index + 1} for index, item in enumerate(matched)]
    limited_items = ranked[:limit]

    payload = {
        "updated_at": now_kst().isoformat(),
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


def analyze_representative_stock(stock: dict[str, str], force_refresh: bool = False) -> dict[str, Any]:
    """유니버스 스캔용 경량 분석. 외부 fetch(뉴스·수급·공시)는 타지 않는다."""
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
    return_5d = return_pct(enriched, 5)
    return_20d = return_pct(enriched, 20)
    volatility_20d = volatility(enriched)
    volume_value_20d = volume_value(enriched)
    liquidity = liquidity_score(enriched)
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
        liquidity_score=liquidity,
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
        "last_analyzed_at": now_kst().isoformat(),
    }
    with _analysis_cache_lock:
        _analysis_cache[cache_key] = (now, dict(item))
    return item


def sort_key(item: dict[str, Any], sort_by: str) -> tuple[Any, ...]:
    signal_rank = SIGNAL_ORDER.get(item["signal"], 99)
    buy_score = int(item.get("buy_score", 0))
    final_buy_score = int(item.get("final_buy_score", buy_score))
    risk_score = int(item.get("risk_score", 100))
    change_rate = float(item.get("change_rate", 0))
    buy_percentile = float(item.get("buy_score_percentile") or 0)
    liquidity = float(item.get("liquidity_score") or 0)
    if sort_by == "buy_score":
        return (-buy_percentile, -final_buy_score, signal_rank, risk_score, -liquidity)
    if sort_by == "risk_score":
        return (risk_score, signal_rank, -buy_percentile, -final_buy_score, -liquidity)
    if sort_by == "change_rate":
        return (-change_rate, signal_rank, -buy_percentile, -final_buy_score, risk_score)
    return (signal_rank, -buy_percentile, -final_buy_score, risk_score, -liquidity)


def failed_item(stock: dict[str, str], message: str) -> dict[str, str]:
    return {
        "name": stock["name"],
        "ticker": stock["ticker"],
        "market": stock["market"],
        "error": message,
        "provider_error": message,
    }


def batched(items: list[dict[str, str]], size: int) -> list[list[dict[str, str]]]:
    return [items[index : index + size] for index in range(0, len(items), size)]


def volatility(enriched) -> float:
    returns = enriched["close"].pct_change().dropna() * 100
    return round(float(returns.tail(20).std()) if len(returns) >= 2 else 0.0, 2)


def volume_value(enriched) -> float:
    value = enriched["close"] * enriched["volume"]
    return round(float(value.tail(20).mean()) if len(value) else 0.0, 2)


def clear_caches() -> None:
    """테스트 격리용. 캐시는 프로세스 수명 내내 살아 있다."""
    with _analysis_cache_lock:
        _analysis_cache.clear()
    with _payload_cache_lock:
        _payload_cache.clear()
