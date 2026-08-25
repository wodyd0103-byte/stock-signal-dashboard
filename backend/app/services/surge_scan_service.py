"""급등 확률 유니버스 스캔.

Triple Barrier 라벨링 기반 급등 확률을 유니버스 전체에 대해 배치로 계산한다.
원래 `app/routers/surge_router.py`의 엔드포인트 안에 있었으나, `scheduler_service`가
캐시 워밍을 위해 라우터를 import해야 했기 때문에 서비스로 옮겼다.

이 모듈은 fastapi를 import하지 않는다. provider와 지표 계산은 `analysis_service`,
유니버스는 `scan_service`의 것을 공유한다 — 인스턴스가 갈리면 캐시도 갈린다.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, wait
from datetime import datetime
from threading import Lock
from typing import Any, Iterator

from app.core.config import get_settings
from app.schemas.surge import SurgeItem
from app.services.analysis_service import data_provider, indicator_service
from app.services.data_provider import DataProviderError
from app.services.scan_service import now_kst, universe_service
from app.services.surge_predictor import SurgePredictor, classify_signal

settings = get_settings()

DISCLAIMER = (
    "급등 확률은 Triple Barrier 라벨링 + 분류 모델의 추정값입니다. "
    "외부 매매 앱에서 실제 매매하기 전 본인 판단으로 확인하세요."
)

# 캐시 (분석 결과 5분 TTL — 동일 매개변수 재호출 시 빠름)
_scan_cache: dict[tuple[str, int, int], tuple[datetime, dict[str, Any]]] = {}
_scan_cache_lock = Lock()
_SCAN_TTL = 300


def analyze_one(stock: dict[str, str], upper: float, lower: float, horizon: int) -> dict[str, Any]:
    """단일 종목 데이터 + 지표 + 급등 예측 (병렬 워커)."""
    predictor = SurgePredictor(upper=upper, lower=lower, horizon=horizon)
    try:
        result = data_provider.fetch_ohlcv(stock["ticker"], "1y")
    except DataProviderError as exc:
        raise RuntimeError(exc.message) from exc

    enriched = indicator_service.enrich(result.data)
    if enriched.empty or len(enriched) < 120:
        raise RuntimeError("데이터 부족")

    pred = predictor.predict(enriched)
    if pred is None:
        raise RuntimeError("예측 불가 (양성 샘플 부족 또는 데이터 부족)")

    latest = enriched.iloc[-1]
    prev = enriched.iloc[-2] if len(enriched) >= 2 else latest
    current_price = float(latest["close"])
    prev_close = float(prev["close"])
    change_rate = ((current_price - prev_close) / prev_close * 100) if prev_close else 0.0

    return {
        "ticker": result.ticker,
        "name": stock.get("name") or result.ticker,
        "market": stock.get("market") or "",
        "current_price": round(current_price, 2),
        "change_rate": round(change_rate, 2),
        "surge_probability": round(pred.surge_probability, 4),
        "base_rate": round(pred.base_rate, 4),
        "lift": round(pred.lift, 3),
        "expected_target_pct": round(pred.upper_pct, 2),
        "horizon_days": pred.horizon_days,
        "signal_label": classify_signal(pred.surge_probability, pred.base_rate),
        "train_samples": pred.train_samples,
        "train_positive": pred.train_positive,
        "cv_score": round(pred.cv_score, 4),
        "reasons": pred.reasons,
        **result.metadata(),
    }


def failed_item(stock: dict[str, str], error: str) -> dict[str, Any]:
    return {
        "ticker": stock.get("ticker", ""),
        "name": stock.get("name", ""),
        "market": stock.get("market", ""),
        "error": error,
    }


def batched(items, size: int) -> Iterator[list]:
    for index in range(0, len(items), size):
        yield items[index : index + size]


def scan(
    market: str = "KR",
    kr_limit: int = 60,
    us_limit: int = 0,
    horizon_days: int = 10,
    upper_pct: float = 10.0,
    lower_pct: float = 5.0,
    limit: int = 30,
    min_probability: float = 0.0,
    force_refresh: bool = False,
) -> dict[str, Any]:
    """유니버스 일괄 스캔 → 급등 확률 순 정렬. 5분 캐시."""
    upper = upper_pct / 100.0
    lower = -abs(lower_pct) / 100.0

    cache_key = (market, kr_limit, horizon_days)
    if not force_refresh:
        with _scan_cache_lock:
            cached = _scan_cache.get(cache_key)
        if cached and (datetime.utcnow() - cached[0]).total_seconds() < _SCAN_TTL:
            return cached[1]

    universe = universe_service.get_representative_stocks(
        market=market, kr_limit=kr_limit, us_limit=us_limit, source="auto",
    )

    successes: list[dict[str, Any]] = []
    failed_items: list[dict[str, Any]] = []

    batch_size = max(1, min(settings.BUY_SIGNAL_BATCH_SIZE, 50))
    max_workers = max(1, min(settings.BUY_SIGNAL_MAX_WORKERS, batch_size, len(universe.items) or 1))

    for batch in batched(universe.items, batch_size):
        workers = max(1, min(max_workers, len(batch)))
        timeout = max(
            settings.BUY_SIGNAL_ITEM_TIMEOUT_SECONDS,
            settings.BUY_SIGNAL_ITEM_TIMEOUT_SECONDS * ((len(batch) + workers - 1) // workers),
        )
        executor = ThreadPoolExecutor(max_workers=workers)
        futures = {
            executor.submit(analyze_one, stock, upper, lower, horizon_days): stock
            for stock in batch
        }
        done, not_done = wait(futures.keys(), timeout=timeout)
        for future in done:
            stock = futures[future]
            try:
                successes.append(future.result())
            except Exception as exc:
                failed_items.append(failed_item(stock, str(exc)))
        for future in not_done:
            stock = futures[future]
            future.cancel()
            failed_items.append(failed_item(stock, f"제한 시간 {timeout}초 초과"))
        executor.shutdown(wait=False, cancel_futures=True)

    # 필터 + 정렬
    filtered = [item for item in successes if item["surge_probability"] >= min_probability]
    filtered.sort(key=lambda item: (item["surge_probability"], item["lift"]), reverse=True)
    ranked = [{**item, "rank": index + 1} for index, item in enumerate(filtered[:limit])]

    payload: dict[str, Any] = {
        "updated_at": now_kst().isoformat(),
        "horizon_days": horizon_days,
        "upper_pct": upper_pct,
        "lower_pct": lower_pct,
        "market": market,
        "items": [SurgeItem(**item).model_dump() for item in ranked],
        "failed": failed_items,
        "total_scanned": len(successes),
        "total_strong": sum(1 for item in successes if item["surge_probability"] >= 0.6),
        "disclaimer": DISCLAIMER,
    }

    with _scan_cache_lock:
        _scan_cache[cache_key] = (datetime.utcnow(), payload)

    return payload


def predict_one(ticker: str, horizon_days: int = 10, upper_pct: float = 10.0, lower_pct: float = 5.0) -> dict[str, Any]:
    """단일 종목 급등 확률. 실패는 RuntimeError로 올라간다."""
    item = analyze_one(
        {"ticker": ticker, "name": ticker, "market": ""},
        upper=upper_pct / 100.0,
        lower=-abs(lower_pct) / 100.0,
        horizon=horizon_days,
    )
    item["rank"] = 1
    return item


def clear_cache() -> None:
    """테스트 격리용."""
    with _scan_cache_lock:
        _scan_cache.clear()
