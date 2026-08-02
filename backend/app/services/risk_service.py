from __future__ import annotations

import numpy as np
import pandas as pd

from app.schemas.analysis import RiskMetric, RiskResponse


class RiskService:
    def analyze(self, ticker: str, period: str, enriched: pd.DataFrame) -> RiskResponse:
        if enriched.empty:
            raise ValueError("리스크를 계산할 가격 데이터가 없습니다.")

        latest = enriched.iloc[-1]
        returns = enriched["close"].pct_change().replace([np.inf, -np.inf], np.nan).dropna()
        volatility = float(returns.tail(20).std() * np.sqrt(252) * 100) if len(returns) > 1 else 0.0
        mdd = self.max_drawdown(enriched["close"])
        recent_20_return = self._pct_change(enriched["close"].iloc[-21], latest["close"]) if len(enriched) > 20 else self._pct_change(enriched["close"].iloc[0], latest["close"])
        volume_drop = bool(latest["volume_change"] < -35)
        price_spike = bool(abs(latest["return_1d"]) > 5 or abs(latest["return_5d"]) > 12)
        ma_break = bool(latest["close"] < latest["ma20"] and latest["ma5"] < latest["ma20"])

        metrics = [
            RiskMetric(
                name="변동성",
                value=round(volatility, 2),
                interpretation="연율화 기준 최근 20거래일 변동성입니다.",
                contribution=self._score(volatility, [(15, 5), (25, 12), (40, 22), (60, 32)]),
            ),
            RiskMetric(
                name="최대 낙폭",
                value=round(mdd, 2),
                interpretation="분석 기간 중 고점 대비 최대 하락률입니다.",
                contribution=self._score(abs(mdd), [(8, 5), (15, 12), (25, 22), (40, 32)]),
            ),
            RiskMetric(
                name="최근 20일 하락률",
                value=round(recent_20_return, 2),
                interpretation="최근 20거래일 가격 변화율입니다.",
                contribution=self._score(abs(min(recent_20_return, 0)), [(5, 4), (10, 10), (18, 18), (30, 26)]),
            ),
            RiskMetric(
                name="거래량 급감 여부",
                value=volume_drop,
                interpretation="최근 거래량이 급감하면 신호 신뢰도가 낮아질 수 있습니다.",
                contribution=12 if volume_drop else 0,
            ),
            RiskMetric(
                name="가격 급등락 여부",
                value=price_spike,
                interpretation="단기 급등락은 변동성 리스크를 높입니다.",
                contribution=14 if price_spike else 0,
            ),
            RiskMetric(
                name="이동평균선 이탈 여부",
                value=ma_break,
                interpretation="현재가와 단기 이동평균이 MA20 아래에 있으면 추세 훼손 가능성이 있습니다.",
                contribution=12 if ma_break else 0,
            ),
        ]
        risk_score = min(100, int(sum(metric.contribution for metric in metrics)))
        level = self.risk_level(risk_score)
        reasons = self._reasons(metrics, level)
        return RiskResponse(ticker=ticker.upper(), period=period, risk_score=risk_score, risk_level=level, metrics=metrics, reasons=reasons)

    def max_drawdown(self, series: pd.Series) -> float:
        if series.empty:
            return 0.0
        cumulative_max = series.cummax()
        drawdown = (series - cumulative_max) / cumulative_max * 100
        return float(drawdown.min())

    def risk_level(self, score: int) -> str:
        if score <= 30:
            return "낮음"
        if score <= 60:
            return "보통"
        if score <= 80:
            return "높음"
        return "매우 높음"

    def _score(self, value: float, bands: list[tuple[float, int]]) -> int:
        score = 0
        for threshold, points in bands:
            if value >= threshold:
                score = points
        return score

    def _pct_change(self, start: float, end: float) -> float:
        if start == 0:
            return 0.0
        return float((end - start) / start * 100)

    def _reasons(self, metrics: list[RiskMetric], level: str) -> list[str]:
        active = [metric for metric in metrics if metric.contribution >= 10]
        if not active:
            return [f"종합 리스크는 {level} 수준이며, 주요 위험 신호는 제한적입니다."]
        reasons = [f"종합 리스크는 {level} 수준입니다."]
        reasons.extend(f"{metric.name}: {metric.interpretation}" for metric in active[:3])
        return reasons
