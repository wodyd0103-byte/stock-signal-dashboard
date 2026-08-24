"""관심종목·보유종목을 모아 분석 결과를 수집한다.

FastAPI 서버를 띄우지 않고 `app/services/analysis_service.py`를 직접 부른다.
DB는 앱과 같은 SQLite 파일을 읽기 전용으로 쓴다 — digest는 아무것도 기록하지 않는다.

출력 포맷은 `render.py`가 담당한다. 여기서는 자료구조까지만 만든다.
"""
from __future__ import annotations

import os
from concurrent.futures import Future, ThreadPoolExecutor, wait
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Iterable, Literal

from app.database import SessionLocal
from app.models.holding import Holding
from app.models.watchlist import WatchlistItem
from app.services import analysis_service
from app.services.analysis_service import AnalysisBundle

Source = Literal["watchlist", "holdings"]
DEFAULT_SOURCES: tuple[Source, ...] = ("watchlist", "holdings")

# 앱 설정(core/config.py)은 서버 런타임용이라 CLI 전용 값을 섞지 않는다.
# analyze() 한 건은 외부 fetch 7종을 병렬로 타므로 buy-signals의 경량 분석보다 느리다.
MAX_WORKERS = max(1, int(os.getenv("DIGEST_MAX_WORKERS", "4")))
ITEM_TIMEOUT_SECONDS = max(1, int(os.getenv("DIGEST_ITEM_TIMEOUT_SECONDS", "40")))


@dataclass
class Target:
    """분석 대상 한 건. 같은 종목이 양쪽에 있으면 sources가 둘 다 담긴다."""

    ticker: str
    name: str | None = None
    sources: list[str] = field(default_factory=list)
    quantity: float | None = None
    avg_price: float | None = None

    @property
    def source_label(self) -> str:
        return "+".join(self.sources)


@dataclass
class Row:
    """분석에 성공한 종목 한 줄."""

    ticker: str
    name: str | None
    sources: list[str]
    current_price: float
    change_rate: float
    signal: str
    buy_score: int
    sell_score: int
    risk_score: int
    risk_level: str
    final_buy_score: int
    market_regime: str | None
    ml_up_probability: float | None
    reasons: list[str]
    # 보유 종목만 채워진다
    quantity: float | None = None
    avg_price: float | None = None
    pnl_pct: float | None = None

    @property
    def source_label(self) -> str:
        return "+".join(self.sources)


@dataclass
class Failure:
    ticker: str
    name: str | None
    sources: list[str]
    error: str


@dataclass
class Digest:
    generated_at: datetime
    period: str
    rows: list[Row]
    failures: list[Failure]
    market_sentiment: dict | None = None

    @property
    def total(self) -> int:
        return len(self.rows) + len(self.failures)


def load_targets(sources: Iterable[str] = DEFAULT_SOURCES) -> list[Target]:
    """DB에서 대상 종목을 읽는다. 같은 티커는 한 건으로 합친다."""
    wanted = set(sources)
    merged: dict[str, Target] = {}

    db = SessionLocal()
    try:
        if "watchlist" in wanted:
            for item in db.query(WatchlistItem).order_by(WatchlistItem.created_at.desc()).all():
                target = merged.setdefault(item.ticker, Target(ticker=item.ticker))
                target.name = target.name or item.name
                target.sources.append("watchlist")

        if "holdings" in wanted:
            for holding in db.query(Holding).order_by(Holding.created_at.desc()).all():
                target = merged.setdefault(holding.ticker, Target(ticker=holding.ticker))
                target.name = target.name or holding.name
                target.sources.append("holdings")
                target.quantity = holding.quantity
                target.avg_price = holding.avg_price
    finally:
        db.close()

    return list(merged.values())


def _row_from_bundle(target: Target, bundle: AnalysisBundle) -> Row:
    quote = bundle.quote
    signal = bundle.signal
    current_price = float(quote["current_price"])

    pnl_pct = None
    if target.avg_price:
        pnl_pct = round((current_price / target.avg_price - 1) * 100, 2)

    return Row(
        ticker=bundle.result.ticker,
        name=target.name,
        sources=list(target.sources),
        current_price=current_price,
        change_rate=float(quote["change_rate"]),
        signal=signal.signal,
        buy_score=signal.buy_score,
        sell_score=signal.sell_score,
        risk_score=signal.risk_score,
        risk_level=bundle.risk.risk_level,
        final_buy_score=signal.final_buy_score,
        market_regime=signal.market_regime,
        ml_up_probability=signal.ml_up_probability,
        reasons=list(signal.reasons or []),
        quantity=target.quantity,
        avg_price=target.avg_price,
        pnl_pct=pnl_pct,
    )


def _sort_key(row: Row) -> tuple[Any, ...]:
    """매수 신호가 강한 순. 같으면 리스크가 낮은 순."""
    order = {
        "STRONG BUY": 0, "BUY": 1, "WEAK BUY": 2, "HOLD": 3,
        "WEAK SELL": 4, "SELL": 5, "STRONG SELL": 6,
    }
    return (order.get(row.signal, 9), -row.final_buy_score, row.risk_score)


def collect(
    sources: Iterable[str] = DEFAULT_SOURCES,
    period: str = "1y",
    max_workers: int = MAX_WORKERS,
    item_timeout: int = ITEM_TIMEOUT_SECONDS,
) -> Digest:
    """대상 종목을 제한 병렬로 분석한다. 일부가 실패해도 나머지는 그대로 돌려준다."""
    targets = load_targets(sources)
    generated_at = datetime.now()
    if not targets:
        return Digest(generated_at=generated_at, period=period, rows=[], failures=[])

    workers = max(1, min(max_workers, len(targets)))
    # 워커가 모자라면 순번을 기다리는 종목이 생긴다. 그만큼 전체 대기시간을 늘린다.
    total_timeout = item_timeout * ((len(targets) + workers - 1) // workers)

    rows: list[Row] = []
    failures: list[Failure] = []

    executor = ThreadPoolExecutor(max_workers=workers)
    try:
        futures: dict[Future, Target] = {
            executor.submit(analysis_service.analyze, target.ticker, period): target
            for target in targets
        }
        done, not_done = wait(futures.keys(), timeout=total_timeout)

        for future in done:
            target = futures[future]
            try:
                rows.append(_row_from_bundle(target, future.result()))
            except Exception as exc:
                failures.append(
                    Failure(ticker=target.ticker, name=target.name, sources=list(target.sources), error=str(exc))
                )

        for future in not_done:
            target = futures[future]
            future.cancel()
            failures.append(
                Failure(
                    ticker=target.ticker,
                    name=target.name,
                    sources=list(target.sources),
                    error=f"분석 제한 시간({total_timeout}초)을 초과했습니다.",
                )
            )
    finally:
        executor.shutdown(wait=False, cancel_futures=True)

    rows.sort(key=_sort_key)
    failures.sort(key=lambda f: f.ticker)

    # 시장 심리는 종목과 무관하다. analyze()가 이미 캐시를 채웠으므로 여기서는 캐시 히트다.
    # 전 종목이 실패해도 헤더에 시장 상황은 남기려고 따로 부른다.
    sentiment = analysis_service.market_sentiment_dict()

    return Digest(
        generated_at=generated_at,
        period=period,
        rows=rows,
        failures=failures,
        market_sentiment=sentiment,
    )
