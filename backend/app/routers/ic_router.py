"""IC 분석 라우터 — 어느 factor가 실제 먹히는지."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query

from app.routers.stock_router import data_provider, indicator_service
from app.services.ic_service import ICService
from app.services.universe_service import UniverseService

router = APIRouter(prefix="/ic", tags=["ic"])
_ic_service = ICService(data_provider, indicator_service, UniverseService())


@router.get("/factors")
def get_factor_ic(
    horizon_days: int = Query(5, ge=1, le=20),
    universe_size: int = Query(40, ge=10, le=100),
    force_refresh: bool = Query(False),
) -> dict[str, Any]:
    """factor별 정보계수(IC). 첫 계산은 수십 초 (유니버스 수집), 이후 6시간 캐시."""
    return _ic_service.compute(horizon_days, universe_size, force=force_refresh).to_dict()
