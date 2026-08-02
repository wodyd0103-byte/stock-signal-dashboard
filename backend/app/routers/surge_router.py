"""
급등주 탐색 라우터.

- `/api/surge/scan` : 유니버스 (KOSPI/KOSDAQ 대표 종목) 일괄 스캔
- `/api/surge/{ticker}` : 단일 종목 급등 확률
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, wait
from datetime import datetime, timezone, timedelta
from threading import Lock
from typing import Any, Literal

from fastapi import APIRouter, HTTPException, Query

from app.core.config import get_settings
from app.schemas.surge import SurgeItem, SurgeScanResponse
from app.services.data_provider import DataProviderError, StockDataProvider
from app.services.indicator_service import IndicatorService
from app.services.surge_predictor import SurgePredictor, classify_signal
from app.services.universe_service import UniverseService


router = APIRouter(prefix="/surge", tags=["surge"])
settings = get_settings()

data_provider = StockDataProvider()
indicator_service = IndicatorService()
universe_service = UniverseService()

DISCLAIMER = (
    "급등 확률은 Triple Barrier 라벨링 + 분류 모델의 추정값입니다. "
    "외부 매매 앱에서 실제 매매하기 전 본인 판단으로 확인하세요."
)

# 캐시 (분석 결과 5분 TTL — 동일 매개변수 재호출 시 빠름)
_scan_cache: dict[tuple[str, int, int], tuple[datetime, dict[str, Any]]] = {}
_scan_cache_lock = Lock()


def _kst_now() -> datetime:
    return datetime.now(timezone(timedelta(hours=9)))


def _analyze_one(stock: dict[str, str], upper: float, lower: float, horizon: int) -> dict[str, Any]:
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


def _failed(stock: dict[str, str], err: str) -> dict[str, Any]:
    return {
        "ticker": stock.get("ticker", ""),
        "name": stock.get("name", ""),
        "market": stock.get("market", ""),
        "error": err,
    }


def _batched(items, size: int):
    for i in range(0, len(items), size):
        yield items[i : i + size]


@router.get("/scan", response_model=SurgeScanResponse)
def scan_surge(
    market: Literal["all", "KR", "US"] = Query("KR"),
    kr_limit: int = Query(60, ge=10, le=200),
    us_limit: int = Query(0, ge=0, le=200),
    horizon_days: int = Query(10, ge=3, le=30),
    upper_pct: float = Query(10.0, ge=3.0, le=30.0),
    lower_pct: float = Query(5.0, ge=2.0, le=20.0),
    limit: int = Query(30, ge=1, le=200),
    min_probability: float = Query(0.0, ge=0.0, le=1.0),
    force_refresh: bool = Query(False),
) -> SurgeScanResponse:
    """유니버스 일괄 스캔 → 급등 확률 순 정렬."""
    upper = upper_pct / 100.0
    lower = -abs(lower_pct) / 100.0

    cache_key = (market, kr_limit, horizon_days)
    if not force_refresh:
        with _scan_cache_lock:
            cached = _scan_cache.get(cache_key)
        if cached and (datetime.utcnow() - cached[0]).total_seconds() < 300:
            return SurgeScanResponse(**cached[1])

    universe = universe_service.get_representative_stocks(
        market=market, kr_limit=kr_limit, us_limit=us_limit, source="auto",
    )

    successes: list[dict[str, Any]] = []
    failed_items: list[dict[str, Any]] = []

    batch_size = max(1, min(settings.BUY_SIGNAL_BATCH_SIZE, 50))
    max_workers = max(1, min(settings.BUY_SIGNAL_MAX_WORKERS, batch_size, len(universe.items) or 1))

    for batch in _batched(universe.items, batch_size):
        workers = max(1, min(max_workers, len(batch)))
        timeout = max(
            settings.BUY_SIGNAL_ITEM_TIMEOUT_SECONDS,
            settings.BUY_SIGNAL_ITEM_TIMEOUT_SECONDS * ((len(batch) + workers - 1) // workers),
        )
        executor = ThreadPoolExecutor(max_workers=workers)
        futures = {
            executor.submit(_analyze_one, stock, upper, lower, horizon_days): stock
            for stock in batch
        }
        done, not_done = wait(futures.keys(), timeout=timeout)
        for fut in done:
            stock = futures[fut]
            try:
                successes.append(fut.result())
            except Exception as exc:
                failed_items.append(_failed(stock, str(exc)))
        for fut in not_done:
            stock = futures[fut]
            fut.cancel()
            failed_items.append(_failed(stock, f"제한 시간 {timeout}초 초과"))
        executor.shutdown(wait=False, cancel_futures=True)

    # 필터 + 정렬
    filtered = [s for s in successes if s["surge_probability"] >= min_probability]
    filtered.sort(key=lambda s: (s["surge_probability"], s["lift"]), reverse=True)
    ranked = [{**s, "rank": i + 1} for i, s in enumerate(filtered[:limit])]

    payload: dict[str, Any] = {
        "updated_at": _kst_now().isoformat(),
        "horizon_days": horizon_days,
        "upper_pct": upper_pct,
        "lower_pct": lower_pct,
        "market": market,
        "items": [SurgeItem(**item).model_dump() for item in ranked],
        "failed": failed_items,
        "total_scanned": len(successes),
        "total_strong": sum(1 for s in successes if s["surge_probability"] >= 0.6),
        "disclaimer": DISCLAIMER,
    }

    with _scan_cache_lock:
        _scan_cache[cache_key] = (datetime.utcnow(), payload)

    return SurgeScanResponse(**payload)


@router.get("/{ticker}", response_model=SurgeItem)
def predict_single(
    ticker: str,
    horizon_days: int = Query(10, ge=3, le=30),
    upper_pct: float = Query(10.0, ge=3.0, le=30.0),
    lower_pct: float = Query(5.0, ge=2.0, le=20.0),
) -> SurgeItem:
    """단일 종목 급등 확률."""
    upper = upper_pct / 100.0
    lower = -abs(lower_pct) / 100.0
    try:
        item = _analyze_one(
            {"ticker": ticker, "name": ticker, "market": ""},
            upper=upper, lower=lower, horizon=horizon_days,
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    item["rank"] = 1
    return SurgeItem(**item)
