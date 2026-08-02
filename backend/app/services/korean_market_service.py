from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

import pandas as pd


@dataclass(frozen=True)
class KoreanMarketContext:
    korean_flow_score: int | None
    liquidity_score_adjustment: int
    risk_score_adjustment: int
    exclude_buy: bool
    reasons: list[str]
    provider_error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "korean_flow_score": self.korean_flow_score,
            "liquidity_score_adjustment": self.liquidity_score_adjustment,
            "risk_score_adjustment": self.risk_score_adjustment,
            "exclude_buy": self.exclude_buy,
            "reasons": self.reasons,
            "provider_error": self.provider_error,
        }


class KoreanMarketService:
    """Optional KR-only flow and risk hooks. Failures never break stock analysis."""

    def analyze(self, ticker: str, enriched: pd.DataFrame, *, fetch_external: bool = False) -> KoreanMarketContext:
        reasons: list[str] = []
        liquidity_adjustment = self._liquidity_adjustment(enriched, reasons)

        if not fetch_external:
            return KoreanMarketContext(
                korean_flow_score=None,
                liquidity_score_adjustment=liquidity_adjustment,
                risk_score_adjustment=0,
                exclude_buy=False,
                reasons=reasons,
            )

        try:
            flow_score, flow_reasons = self._fetch_flow_score(ticker)
            reasons.extend(flow_reasons)
            return KoreanMarketContext(
                korean_flow_score=flow_score,
                liquidity_score_adjustment=liquidity_adjustment,
                risk_score_adjustment=0,
                exclude_buy=False,
                reasons=reasons,
            )
        except Exception as exc:
            return KoreanMarketContext(
                korean_flow_score=None,
                liquidity_score_adjustment=liquidity_adjustment,
                risk_score_adjustment=0,
                exclude_buy=False,
                reasons=reasons,
                provider_error=f"{type(exc).__name__}: {exc}",
            )

    def _liquidity_adjustment(self, enriched: pd.DataFrame, reasons: list[str]) -> int:
        if enriched.empty or len(enriched) < 20:
            return 0
        latest = enriched.iloc[-1]
        recent_value = float(latest["close"]) * float(latest["volume"])
        avg_value = float((enriched["close"] * enriched["volume"]).tail(20).mean())
        if avg_value > 0 and recent_value / avg_value >= 1.5:
            reasons.append("거래대금이 20일 평균 대비 150% 이상으로 증가해 유동성 점수를 보강했습니다.")
            return 10
        return 0

    def _fetch_flow_score(self, ticker: str) -> tuple[int, list[str]]:
        from pykrx import stock

        end = datetime.utcnow().date()
        start = end - timedelta(days=10)
        raw = stock.get_market_trading_value_by_date(start.strftime("%Y%m%d"), end.strftime("%Y%m%d"), ticker)
        if raw.empty:
            return 0, ["수급 데이터가 비어 있어 수급 점수는 반영하지 않았습니다."]

        score = 0
        reasons: list[str] = []
        tail = raw.tail(3)
        foreign_column = next((column for column in tail.columns if "외국인" in str(column)), None)
        institution_column = next((column for column in tail.columns if "기관" in str(column)), None)

        foreign_positive = bool(foreign_column and (pd.to_numeric(tail[foreign_column], errors="coerce") > 0).all())
        institution_positive = bool(institution_column and (pd.to_numeric(tail[institution_column], errors="coerce") > 0).all())

        if foreign_positive:
            score += 5
            reasons.append("외국인이 최근 3거래일 연속 순매수했습니다.")
        if institution_positive:
            score += 5
            reasons.append("기관이 최근 3거래일 연속 순매수했습니다.")
        if foreign_positive and institution_positive:
            score += 8
            reasons.append("외국인과 기관이 동시에 순매수해 수급 점수를 추가 보강했습니다.")
        return min(score, 18), reasons
