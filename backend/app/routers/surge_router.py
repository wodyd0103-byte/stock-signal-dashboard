"""
급등주 탐색 라우터.

- `/api/surge/scan` : 유니버스 (KOSPI/KOSDAQ 대표 종목) 일괄 스캔
- `/api/surge/{ticker}` : 단일 종목 급등 확률

스캔 로직은 `app/services/surge_scan_service.py`에 있다. 여기서는 매개변수 검증과
HTTP 변환만 한다.
"""
from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, HTTPException, Query

from app.schemas.surge import SurgeItem, SurgeScanResponse
from app.services import surge_scan_service

router = APIRouter(prefix="/surge", tags=["surge"])


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
    payload = surge_scan_service.scan(
        market=market,
        kr_limit=kr_limit,
        us_limit=us_limit,
        horizon_days=horizon_days,
        upper_pct=upper_pct,
        lower_pct=lower_pct,
        limit=limit,
        min_probability=min_probability,
        force_refresh=force_refresh,
    )
    return SurgeScanResponse(**payload)


@router.get("/{ticker}", response_model=SurgeItem)
def predict_single(
    ticker: str,
    horizon_days: int = Query(10, ge=3, le=30),
    upper_pct: float = Query(10.0, ge=3.0, le=30.0),
    lower_pct: float = Query(5.0, ge=2.0, le=20.0),
) -> SurgeItem:
    """단일 종목 급등 확률."""
    try:
        item = surge_scan_service.predict_one(
            ticker,
            horizon_days=horizon_days,
            upper_pct=upper_pct,
            lower_pct=lower_pct,
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return SurgeItem(**item)
