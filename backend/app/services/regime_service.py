from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

import numpy as np
import pandas as pd


MarketRegime = Literal["BULL_TREND", "BEAR_TREND", "SIDEWAYS", "HIGH_VOLATILITY", "RECOVERY", "BEAR_CRASH"]


@dataclass(frozen=True)
class RegimeResult:
    market_regime: MarketRegime
    regime_score: int
    description: str
    adjustments: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "market_regime": self.market_regime,
            "regime_score": self.regime_score,
            "description": self.description,
            "adjustments": self.adjustments,
        }


class RegimeService:
    def analyze_from_frame(self, enriched: pd.DataFrame) -> RegimeResult:
        if enriched.empty or len(enriched) < 30:
            return self._sideways("시장국면 판단에 필요한 데이터가 부족해 중립 국면으로 처리했습니다.")

        frame = enriched.copy().sort_values("date").reset_index(drop=True)
        close = pd.to_numeric(frame["close"], errors="coerce")
        ma20 = close.rolling(20, min_periods=5).mean()
        ma60 = close.rolling(60, min_periods=20).mean()
        returns = close.pct_change() * 100
        return_5d = self._pct_change(close, 5)
        return_20d = self._pct_change(close, 20)
        volatility_20d = float(returns.tail(20).std()) if len(returns.dropna()) >= 20 else 0.0
        volatility_threshold = float(returns.rolling(20, min_periods=20).std().dropna().quantile(0.8) or 0.0)

        latest_close = float(close.iloc[-1])
        latest_ma20 = float(ma20.iloc[-1]) if pd.notna(ma20.iloc[-1]) else latest_close
        latest_ma60 = float(ma60.iloc[-1]) if pd.notna(ma60.iloc[-1]) else latest_ma20
        previous_close = float(close.iloc[-2]) if len(close) > 1 else latest_close
        previous_ma20 = float(ma20.iloc[-2]) if len(ma20) > 1 and pd.notna(ma20.iloc[-2]) else latest_ma20

        if return_20d <= -12 and latest_close < latest_ma20 < latest_ma60:
            return RegimeResult(
                market_regime="BEAR_CRASH",
                regime_score=-25,
                description="20일 수익률이 크게 하락하고 주요 이동평균 아래에 있어 급락장으로 분류했습니다.",
                adjustments=["급락장에서는 강한 매수 후보만 통과하도록 기준을 강화합니다.", "리스크 점수의 영향이 커집니다."],
            )
        if volatility_threshold and volatility_20d >= volatility_threshold and volatility_20d >= 2.5:
            return RegimeResult(
                market_regime="HIGH_VOLATILITY",
                regime_score=-15,
                description="최근 변동성이 1년 분포 상위권에 있어 고변동성 국면으로 분류했습니다.",
                adjustments=["고변동성 국면에서는 리스크가 높은 매수 후보를 보수적으로 처리합니다."],
            )
        if latest_close > latest_ma20 > latest_ma60 and return_20d > 0:
            return RegimeResult(
                market_regime="BULL_TREND",
                regime_score=12,
                description="가격이 MA20과 MA60 위에 있고 20일 수익률이 양수여서 상승 추세로 분류했습니다.",
                adjustments=["추세 지속형 점수와 돌파형 점수의 가중치를 높입니다."],
            )
        if latest_close < latest_ma20 < latest_ma60 and return_20d < 0:
            return RegimeResult(
                market_regime="BEAR_TREND",
                regime_score=-12,
                description="가격이 주요 이동평균 아래에 있고 20일 수익률이 음수여서 하락 추세로 분류했습니다.",
                adjustments=["하락 추세에서는 매수 기준을 강화하고 리스크를 더 크게 반영합니다."],
            )
        if previous_close <= previous_ma20 and latest_close > latest_ma20 and return_5d > 0:
            return RegimeResult(
                market_regime="RECOVERY",
                regime_score=8,
                description="가격이 MA20을 회복했고 최근 5일 수익률이 양수여서 회복 국면으로 분류했습니다.",
                adjustments=["반등형 신호와 거래량 동반 회복 점수의 영향이 커집니다."],
            )
        return self._sideways("뚜렷한 추세가 확인되지 않아 횡보장으로 분류했습니다.")

    def analyze_universe(self, items: list[dict[str, Any]], market: str = "all") -> RegimeResult:
        if not items:
            return self._sideways("분석된 종목이 없어 중립 국면으로 처리했습니다.")

        frame = pd.DataFrame(items)
        return_20d = float(pd.to_numeric(frame.get("return_20d"), errors="coerce").dropna().mean() or 0.0)
        return_5d = float(pd.to_numeric(frame.get("return_5d"), errors="coerce").dropna().mean() or 0.0)
        volatility = float(pd.to_numeric(frame.get("volatility_20d"), errors="coerce").dropna().mean() or 0.0)
        positive_ratio = float((pd.to_numeric(frame.get("return_20d"), errors="coerce") > 0).mean() or 0.0)

        if return_20d <= -10 and positive_ratio < 0.25:
            return RegimeResult("BEAR_CRASH", -25, "대표 종목 다수가 20일 기준 약세여서 급락장에 가깝게 분류했습니다.", ["상대순위가 높아도 리스크가 큰 종목은 매수 후보에서 제외합니다."])
        if volatility >= 3.0:
            return RegimeResult("HIGH_VOLATILITY", -15, "대표 종목 평균 변동성이 높아 고변동성 국면으로 분류했습니다.", ["강한 매수 신호만 통과하도록 기준을 강화합니다."])
        if return_20d > 3 and positive_ratio >= 0.6:
            return RegimeResult("BULL_TREND", 12, "대표 종목 다수가 20일 기준 상승해 상승 추세로 분류했습니다.", ["추세형 후보의 최종 매수 점수를 보강합니다."])
        if return_20d < -3 and positive_ratio <= 0.4:
            return RegimeResult("BEAR_TREND", -12, "대표 종목 다수가 20일 기준 하락해 하락 추세로 분류했습니다.", ["매수 기준을 강화하고 리스크를 더 크게 반영합니다."])
        if return_5d > 1.5 and return_20d < 0:
            return RegimeResult("RECOVERY", 8, "20일 흐름은 약했지만 최근 5일 평균 수익률이 개선되어 회복 국면으로 분류했습니다.", ["반등형 후보에 일부 가중치를 부여합니다."])
        return self._sideways("대표 종목 평균 흐름이 뚜렷하지 않아 횡보장으로 분류했습니다.")

    def _pct_change(self, series: pd.Series, days: int) -> float:
        if len(series) <= days or float(series.iloc[-days - 1]) == 0:
            return 0.0
        return float((series.iloc[-1] / series.iloc[-days - 1] - 1) * 100)

    def _sideways(self, description: str) -> RegimeResult:
        return RegimeResult(
            market_regime="SIDEWAYS",
            regime_score=0,
            description=description,
            adjustments=["횡보장에서는 RSI, Bollinger Band 등 평균회귀형 신호를 조금 더 봅니다."],
        )
