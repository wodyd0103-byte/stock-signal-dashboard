"""
CSV 내보내기 라우터.
외부 매매 앱으로 가져갈 분석 결과를 CSV로 다운로드.
"""
from __future__ import annotations

import csv
import io
from datetime import datetime
from typing import Iterable, Sequence

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.watchlist import WatchlistItem
from app.services.scan_service import buy_signals_payload
from app.routers import analysis_http
from app.services.analysis_service import load_enriched, prediction_service, quote_from_frame, risk_service, signal_service

router = APIRouter(prefix="/export", tags=["export"])


_CSV_INJECTION_PREFIXES = ("=", "+", "-", "@", "\t", "\r")


def _csv_safe(value: object) -> object:
    """CSV 수식 주입(formula injection) 방어.

    외부 출처(종목명/뉴스/사유)가 '=','+','-','@' 등으로 시작하면 Excel/Sheets가
    수식으로 해석·실행할 수 있음 → 앞에 작은따옴표를 붙여 텍스트로 강제.
    """
    if isinstance(value, str) and value and value[0] in _CSV_INJECTION_PREFIXES:
        return "'" + value
    return value


def _to_csv_stream(headers: Sequence[str], rows: Iterable[Sequence[object]]) -> StreamingResponse:
    """UTF-8 BOM 포함 (엑셀 한글 깨짐 방지)."""
    buf = io.StringIO()
    buf.write("﻿")  # BOM for Excel
    writer = csv.writer(buf, lineterminator="\n")
    writer.writerow(headers)
    for row in rows:
        writer.writerow([_csv_safe(cell) for cell in row])
    buf.seek(0)

    filename = f"export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/buy-signals.csv")
def export_buy_signals(
    market: str = Query("all"),
    min_signal: str = Query("BUY"),
    kr_limit: int = Query(100, ge=1, le=500),
    us_limit: int = Query(100, ge=1, le=500),
    limit: int = Query(50, ge=1, le=500),
    include_sample: bool = Query(False),
    source: str = Query("auto"),
    sort_by: str = Query("signal"),
    force_refresh: bool = Query(False),
) -> StreamingResponse:
    """매수 신호 결과를 CSV로 다운로드."""
    payload = buy_signals_payload(
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
    items = payload.get("items", [])

    headers = [
        "rank", "ticker", "name", "market", "current_price", "change_rate(%)",
        "signal", "buy_score", "sell_score", "risk_score",
        "buy_score_zone", "risk_score_zone", "market_regime",
        "ml_up_probability", "model_confidence",
        "reasons", "hold_reasons", "last_analyzed_at",
    ]
    rows = []
    for item in items:
        rows.append([
            item.get("rank"),
            item.get("ticker"),
            item.get("name"),
            item.get("market"),
            item.get("current_price"),
            item.get("change_rate"),
            item.get("signal"),
            item.get("buy_score"),
            item.get("sell_score"),
            item.get("risk_score"),
            item.get("buy_score_zone"),
            item.get("risk_score_zone"),
            item.get("market_regime"),
            item.get("ml_up_probability"),
            item.get("model_confidence"),
            " | ".join(item.get("reasons", []) or []),
            " | ".join(item.get("hold_reasons", []) or []),
            item.get("last_analyzed_at"),
        ])
    return _to_csv_stream(headers, rows)


@router.get("/watchlist.csv")
def export_watchlist(db: Session = Depends(get_db)) -> StreamingResponse:
    """관심종목 분석 결과를 CSV로 다운로드."""
    items = db.query(WatchlistItem).order_by(WatchlistItem.created_at.desc()).all()

    headers = [
        "ticker", "name", "current_price", "change_rate(%)",
        "signal", "buy_score", "sell_score", "risk_score",
        "expected_return_5d(%)", "confidence_5d",
        "risk_level", "reasons", "analyzed_at", "error",
    ]
    rows = []
    for it in items:
        try:
            result, enriched = load_enriched(it.ticker, "1y")
            quote = quote_from_frame(result, "1y", enriched)
            risk = risk_service.analyze(result.ticker, "1y", enriched)
            prediction = prediction_service.predict(result.ticker, "1y", enriched)
            signal = signal_service.score(enriched, risk.risk_score, prediction)
            # 5일 예측 추출
            h5 = next((p for p in prediction.predictions if p.horizon_days == 5), None)
            rows.append([
                it.ticker,
                it.name or "",
                quote["current_price"],
                quote["change_rate"],
                signal.signal,
                signal.buy_score,
                signal.sell_score,
                signal.risk_score,
                round(h5.expected_return_pct, 2) if h5 else "",
                h5.confidence_score if h5 else "",
                risk.risk_level,
                " | ".join((signal.reasons or [])[:3]),
                datetime.utcnow().isoformat(timespec="seconds"),
                "",
            ])
        except Exception as exc:
            rows.append([
                it.ticker, it.name or "", "", "", "", "", "", "", "", "", "", "", "", str(exc),
            ])
    return _to_csv_stream(headers, rows)


@router.get("/stock/{ticker}.csv")
def export_stock_analysis(ticker: str, period: str = Query("1y")) -> StreamingResponse:
    """단일 종목의 가격 + 지표 + 신호 시계열을 CSV로."""
    result, enriched = analysis_http.load_enriched(ticker, period)
    if enriched.empty:
        return _to_csv_stream(["error"], [["빈 데이터"]])

    df = enriched.copy()
    df = df.reset_index()
    # 컬럼 정리
    cols = [c for c in df.columns if c.lower() not in ("level_0", "index")]
    df = df[cols]
    headers = list(df.columns.astype(str))
    rows = []
    for _, r in df.iterrows():
        rows.append([
            r[c].isoformat() if hasattr(r[c], "isoformat") else r[c]
            for c in df.columns
        ])
    return _to_csv_stream(headers, rows)
