import logging
import time
import uuid

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.database import init_db
from app.routers import export_router, ic_router, market_router, portfolio_router, retrospective_router, stock_router, surge_router, watchlist_router
from app.schemas.stock import HealthResponse
from app.services.scheduler_service import run_now as scheduler_run_now
from app.services.scheduler_service import start_scheduler, stop_scheduler


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

request_logger = logging.getLogger("request")
SLOW_REQUEST_MS = 2000  # 이 이상 걸리면 WARNING


settings = get_settings()

app = FastAPI(
    title=settings.PROJECT_NAME,
    description="과거 데이터와 알고리즘 기반 투자 참고용 분석 API",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    """구조적 요청 로깅 — 메서드/경로/상태/소요시간(ms)/요청ID. 느린 요청은 WARNING."""
    rid = uuid.uuid4().hex[:8]
    start = time.perf_counter()
    try:
        response = await call_next(request)
    except Exception:
        dur = (time.perf_counter() - start) * 1000
        request_logger.exception(
            f"rid={rid} method={request.method} path={request.url.path} status=500 dur_ms={dur:.0f} error=unhandled"
        )
        raise
    dur = (time.perf_counter() - start) * 1000
    level = logging.WARNING if dur > SLOW_REQUEST_MS else logging.INFO
    request_logger.log(
        level,
        f"rid={rid} method={request.method} path={request.url.path} status={response.status_code} dur_ms={dur:.0f}",
    )
    response.headers["X-Request-ID"] = rid
    return response


@app.on_event("startup")
def on_startup() -> None:
    init_db()
    start_scheduler()


@app.on_event("shutdown")
def on_shutdown() -> None:
    stop_scheduler()


@app.post(f"{settings.API_PREFIX}/admin/refresh-now")
def refresh_now() -> dict:
    """수동 분석 갱신 트리거 (디버그/관리자용)."""
    return scheduler_run_now()


@app.get(f"{settings.API_PREFIX}/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse()


app.include_router(stock_router.router, prefix=settings.API_PREFIX)
app.include_router(stock_router.debug_router, prefix=settings.API_PREFIX)
app.include_router(market_router.router, prefix=settings.API_PREFIX)
app.include_router(watchlist_router.router, prefix=settings.API_PREFIX)
app.include_router(export_router.router, prefix=settings.API_PREFIX)
app.include_router(surge_router.router, prefix=settings.API_PREFIX)
app.include_router(ic_router.router, prefix=settings.API_PREFIX)
app.include_router(retrospective_router.router, prefix=settings.API_PREFIX)
app.include_router(portfolio_router.router, prefix=settings.API_PREFIX)
