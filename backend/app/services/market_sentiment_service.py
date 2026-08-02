"""
시장 심리 / 공포·탐욕 지수 서비스.

VKOSPI 직접 접근 불가 (KRX 인증) → 다중 지표로 자체 공포·탐욕 지수 구성.
CNN Fear & Greed 방식: 0(극도 공포) ~ 100(극도 탐욕).

구성 요소 (각 0~100, 가중 평균):
1. VIX (글로벌 공포)        — 낮을수록 탐욕
2. KOSPI 실현변동성 (20일)  — 낮을수록 탐욕 (VKOSPI 대용)
3. USD/KRW 변동성           — 원화 안정 = 탐욕
4. KOSPI 추세 (MA60 이격)   — 위 = 탐욕
5. KOSPI 모멘텀 (20일 수익) — 양 = 탐욕

데이터: FinanceDataReader (VIX, KS11, USD/KRW)
캐시: 1시간 (시장 전체 공통값)
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from threading import Lock

import numpy as np
import pandas as pd

logger = logging.getLogger("market_sentiment")

_cache: dict[str, tuple[datetime, "MarketSentiment"]] = {}
_cache_lock = Lock()
_CACHE_TTL_SECONDS = 3600


@dataclass
class SentimentComponent:
    name: str
    raw_value: float          # 원시값 (VIX 16.4, 변동성 18.2% 등)
    score: float              # 0~100 (높을수록 탐욕)
    interpretation: str


@dataclass
class MarketSentiment:
    score: int                # 0~100 종합 (0=극도공포, 100=극도탐욕)
    label: str                # "극도 공포" ~ "극도 탐욕"
    risk_on: bool             # 위험선호 여부 (score >= 50)
    components: list[SentimentComponent]
    updated_at: str

    def to_dict(self) -> dict:
        return {
            "score": self.score,
            "label": self.label,
            "risk_on": self.risk_on,
            "components": [
                {
                    "name": c.name,
                    "raw_value": round(c.raw_value, 2),
                    "score": round(c.score, 1),
                    "interpretation": c.interpretation,
                }
                for c in self.components
            ],
            "updated_at": self.updated_at,
        }


def _clamp(v: float) -> float:
    return max(0.0, min(100.0, v))


def _linear_score(value: float, low: float, high: float, invert: bool = False) -> float:
    """value를 [low, high] 구간에서 0~100으로 선형 매핑.
    invert=True → 낮은 값이 높은 점수 (공포지표는 낮을수록 탐욕)."""
    if high == low:
        return 50.0
    pct = (value - low) / (high - low) * 100
    pct = _clamp(pct)
    return 100 - pct if invert else pct


def _label(score: int) -> str:
    if score <= 24: return "극도 공포"
    if score <= 44: return "공포"
    if score <= 55: return "중립"
    if score <= 74: return "탐욕"
    return "극도 탐욕"


class MarketSentimentService:
    def get(self, force_refresh: bool = False) -> MarketSentiment:
        if not force_refresh:
            with _cache_lock:
                cached = _cache.get("kr")
            if cached and (datetime.utcnow() - cached[0]).total_seconds() < _CACHE_TTL_SECONDS:
                return cached[1]

        sentiment = self._compute()
        with _cache_lock:
            _cache["kr"] = (datetime.utcnow(), sentiment)
        return sentiment

    def _compute(self) -> MarketSentiment:
        import FinanceDataReader as fdr

        components: list[SentimentComponent] = []
        weights: list[float] = []

        # ── 1. VIX (글로벌 공포) ──────────────────────
        try:
            vix = fdr.DataReader("VIX", "2024")["Close"].dropna()
            vix_val = float(vix.iloc[-1])
            # VIX 12(탐욕) ~ 40(공포). 낮을수록 탐욕
            vix_score = _linear_score(vix_val, 12, 40, invert=True)
            components.append(SentimentComponent(
                name="VIX (글로벌 공포지수)",
                raw_value=vix_val,
                score=vix_score,
                interpretation=self._vix_text(vix_val),
            ))
            weights.append(0.25)
        except Exception as exc:
            logger.warning(f"VIX 수집 실패: {exc}")

        # ── 2. KOSPI 실현변동성 (VKOSPI 대용) ─────────
        try:
            kospi = fdr.DataReader("KS11", "2024")["Close"].dropna()
            ret = kospi.pct_change().dropna()
            realized_vol = float(ret.tail(20).std() * np.sqrt(252) * 100)
            # 연율 변동성 10%(탐욕) ~ 35%(공포)
            vol_score = _linear_score(realized_vol, 10, 35, invert=True)
            components.append(SentimentComponent(
                name="KOSPI 변동성 (VKOSPI 대용)",
                raw_value=realized_vol,
                score=vol_score,
                interpretation=f"최근 20일 연율 변동성 {realized_vol:.1f}%",
            ))
            weights.append(0.25)

            # ── 4. KOSPI 추세 (MA60 이격) ──────────────
            ma60 = kospi.rolling(60).mean()
            disparity = float(kospi.iloc[-1] / ma60.iloc[-1] - 1) * 100
            # -8%(공포) ~ +8%(탐욕)
            trend_score = _linear_score(disparity, -8, 8)
            components.append(SentimentComponent(
                name="KOSPI 추세 (MA60 이격도)",
                raw_value=disparity,
                score=trend_score,
                interpretation=f"60일 이평 대비 {disparity:+.2f}%",
            ))
            weights.append(0.2)

            # ── 5. KOSPI 모멘텀 (20일 수익률) ──────────
            momentum = float(kospi.iloc[-1] / kospi.iloc[-21] - 1) * 100 if len(kospi) > 21 else 0.0
            mom_score = _linear_score(momentum, -10, 10)
            components.append(SentimentComponent(
                name="KOSPI 모멘텀 (20일)",
                raw_value=momentum,
                score=mom_score,
                interpretation=f"최근 20일 수익률 {momentum:+.2f}%",
            ))
            weights.append(0.15)
        except Exception as exc:
            logger.warning(f"KOSPI 지표 수집 실패: {exc}")

        # ── 3. USD/KRW 변동성 (원화 스트레스) ─────────
        try:
            usdkrw = fdr.DataReader("USD/KRW", "2024")["Close"].dropna()
            fx_ret = usdkrw.pct_change().dropna()
            fx_vol = float(fx_ret.tail(20).std() * np.sqrt(252) * 100)
            # 환율 변동성 4%(안정/탐욕) ~ 15%(불안/공포)
            fx_score = _linear_score(fx_vol, 4, 15, invert=True)
            components.append(SentimentComponent(
                name="원/달러 변동성",
                raw_value=fx_vol,
                score=fx_score,
                interpretation=f"환율 연율 변동성 {fx_vol:.1f}% (현재 {usdkrw.iloc[-1]:.0f}원)",
            ))
            weights.append(0.15)
        except Exception as exc:
            logger.warning(f"USD/KRW 수집 실패: {exc}")

        # ── 종합 (가중 평균) ──────────────────────────
        if not components:
            # 전부 실패 → 중립 fallback
            return MarketSentiment(
                score=50, label="중립 (데이터 없음)", risk_on=True,
                components=[], updated_at=datetime.now().isoformat(timespec="seconds"),
            )

        total_w = sum(weights)
        weighted = sum(c.score * w for c, w in zip(components, weights)) / total_w
        final = int(round(_clamp(weighted)))

        return MarketSentiment(
            score=final,
            label=_label(final),
            risk_on=final >= 50,
            components=components,
            updated_at=datetime.now().isoformat(timespec="seconds"),
        )

    def _vix_text(self, vix: float) -> str:
        if vix >= 30: return f"VIX {vix:.1f} — 시장 공포 고조"
        if vix >= 20: return f"VIX {vix:.1f} — 변동성 경계"
        if vix >= 15: return f"VIX {vix:.1f} — 정상 범위"
        return f"VIX {vix:.1f} — 낙관 (저변동성)"
