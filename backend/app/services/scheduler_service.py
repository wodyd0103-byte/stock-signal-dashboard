"""
APScheduler 기반 분석 갱신 스케줄러.

- 매매 X. 분석 캐시만 사전 워밍 → 사용자가 페이지 열 때 즉시 결과.
- KST 기준 평일 장 마감 후 1회 일괄 분석.
- 외부 매매 앱 워크플로 보조: 마감 후 → 신호 갱신 → 익일 아침 사용자 검토.

ENV:
  SCHEDULER_ENABLED=true        # 활성화 (default false)
  SCHEDULER_REFRESH_HOUR=16     # KST 정각 (default 16)
  SCHEDULER_REFRESH_MINUTE=00   # default 0
  SCHEDULER_DAYS=mon,tue,wed,thu,fri  # default 평일
"""
from __future__ import annotations

import logging
import os
from datetime import datetime
from typing import Optional

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

logger = logging.getLogger("scheduler")


_scheduler: Optional[BackgroundScheduler] = None


def _enabled() -> bool:
    return os.getenv("SCHEDULER_ENABLED", "false").lower() in {"1", "true", "yes", "on"}


def _refresh_analysis_cache() -> None:
    """매수 신호 + 관심종목 분석을 백그라운드에서 미리 계산."""
    from app.database import SessionLocal
    from app.models.watchlist import WatchlistItem
    from app.services.scan_service import buy_signals_payload
    from app.services.analysis_service import load_enriched, prediction_service, risk_service, signal_service

    start = datetime.now()
    logger.info("[scheduler] 분석 갱신 시작")

    # 0. 시장 공포·탐욕 지수 캐시 워밍 (콜드 4 FDR 호출 선처리)
    try:
        from app.services.market_sentiment_service import MarketSentimentService
        s = MarketSentimentService().get(force_refresh=True)
        logger.info(f"[scheduler] 시장 심리 갱신: {s.score}/100 [{s.label}]")
    except Exception as exc:
        logger.warning(f"[scheduler] 시장 심리 갱신 실패: {exc}")

    # 1. 매수 신호 캐시 워밍 (all + 발굴탭이 쓰는 KR 둘 다)
    try:
        result = buy_signals_payload(
            market="all", min_signal="WEAK_BUY",
            kr_limit=100, us_limit=100, limit=100,
            include_sample=False, source="auto",
            sort_by="signal", force_refresh=True,
        )
        # 발굴 레일과 동일 파라미터 (market=KR, limit=30) → 첫 로드 즉시
        buy_signals_payload(
            market="KR", min_signal="WEAK_BUY",
            kr_limit=100, us_limit=100, limit=30,
            include_sample=False, source="auto",
            sort_by="signal", force_refresh=False,
        )
        logger.info(f"[scheduler] 매수신호 {result.get('total_matched', 0)}건 갱신")
    except Exception as exc:
        logger.exception(f"[scheduler] 매수신호 갱신 실패: {exc}")

    # 1-b. 급등 탐색 캐시 워밍 (발굴 레일 KR 파라미터)
    try:
        from app.routers.surge_router import scan_surge
        scan_surge(market="KR", kr_limit=60, us_limit=0, horizon_days=10,
                   upper_pct=10.0, lower_pct=5.0, limit=30,
                   min_probability=0.2, force_refresh=True)
        logger.info("[scheduler] 급등 탐색 갱신")
    except Exception as exc:
        logger.warning(f"[scheduler] 급등 탐색 갱신 실패: {exc}")

    # 2. 관심종목 캐시 워밍
    db = SessionLocal()
    try:
        items = db.query(WatchlistItem).all()
        for it in items:
            try:
                _, enriched = load_enriched(it.ticker, "1y")
                risk = risk_service.analyze(it.ticker, "1y", enriched)
                pred = prediction_service.predict(it.ticker, "1y", enriched)
                signal_service.score(enriched, risk.risk_score, pred)
            except Exception as exc:
                logger.warning(f"[scheduler] {it.ticker} 갱신 실패: {exc}")
        logger.info(f"[scheduler] 관심종목 {len(items)}건 갱신")
    finally:
        db.close()

    # 3. 회고 채점 (horizon 경과 추천 평가)
    db2 = SessionLocal()
    try:
        from app.services.analysis_service import data_provider
        from app.services.retrospective_service import RetrospectiveService

        def _price(ticker: str):
            res = data_provider.fetch_ohlcv(ticker, "1mo")
            if res.data is not None and not res.data.empty:
                return float(res.data.iloc[-1]["close"])
            return None

        n = RetrospectiveService().evaluate_due(db2, _price)
        logger.info(f"[scheduler] 회고 채점 {n}건")
    except Exception as exc:
        logger.warning(f"[scheduler] 회고 채점 실패: {exc}")
    finally:
        db2.close()

    elapsed = (datetime.now() - start).total_seconds()
    logger.info(f"[scheduler] 갱신 완료 ({elapsed:.1f}초)")


def start_scheduler() -> None:
    """앱 시작 시 호출. SCHEDULER_ENABLED=true 일 때만 작동."""
    global _scheduler
    if not _enabled():
        logger.info("[scheduler] 비활성 (SCHEDULER_ENABLED=true 로 켜기)")
        return
    if _scheduler is not None:
        return

    hour = int(os.getenv("SCHEDULER_REFRESH_HOUR", "16"))
    minute = int(os.getenv("SCHEDULER_REFRESH_MINUTE", "0"))
    days = os.getenv("SCHEDULER_DAYS", "mon,tue,wed,thu,fri")

    _scheduler = BackgroundScheduler(timezone="Asia/Seoul")
    _scheduler.add_job(
        _refresh_analysis_cache,
        trigger=CronTrigger(day_of_week=days, hour=hour, minute=minute),
        id="analysis_refresh",
        replace_existing=True,
        misfire_grace_time=600,  # 10분 늦어도 실행
    )
    _scheduler.start()
    logger.info(f"[scheduler] 시작 — {days} {hour:02d}:{minute:02d} KST (분석 갱신)")


def stop_scheduler() -> None:
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None
        logger.info("[scheduler] 종료")


def run_now() -> dict:
    """수동 트리거 (디버그/관리자용)."""
    _refresh_analysis_cache()
    return {"status": "ok", "ran_at": datetime.now().isoformat()}
