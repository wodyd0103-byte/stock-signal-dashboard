"""
학습 기반 신호 — IC 가중 factor 합성.

손튜닝 점수(18/16/12...) 대신, IC 분석이 검증한 factor를 IC 크기·부호로 가중.
- IC 캐시(ICService)에서 factor별 IC 가져옴
- |IC| >= 임계 factor만 채택 (무의미한 것 버림)
- 종목의 factor 값을 횡단면 z-score로 표준화 → IC 부호·크기 가중합 → 0~100 점수

장점: 데이터가 가중치 결정 (감 아님). IC 0이면 자동 배제.
한계: IC 표본/기간 의존. price-derived factor만. 보조 점수로 제공.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

import numpy as np
import pandas as pd

logger = logging.getLogger("learned_signal")

_MIN_ABS_IC = 0.015  # 이 미만 IC factor는 무시


@dataclass
class LearnedSignal:
    score: float            # 0~100 (50 중립, 높을수록 매수 우호)
    label: str
    contributions: list[dict]  # factor별 기여 [{factor, ic, z, contrib}]
    used_factors: int
    note: str

    def to_dict(self) -> dict:
        return {
            "score": round(self.score, 1),
            "label": self.label,
            "used_factors": self.used_factors,
            "contributions": self.contributions,
            "note": self.note,
        }


class LearnedSignalService:
    def __init__(self, ic_service):
        self.ic_service = ic_service
        # 횡단면 표준화용 모집단 통계 캐시 (factor → (mean,std))
        self._pop_stats: dict[str, tuple[float, float]] = {}

    def _factor_values(self, enriched: pd.DataFrame) -> dict[str, float]:
        """ic_service의 factor 정의와 동일한 최신 factor 값."""
        c = enriched["close"]
        latest = enriched.iloc[-1]
        try:
            band_w = float(latest["bollinger_upper"] - latest["bollinger_lower"]) or np.nan
            band_pos = (float(latest["close"]) - float(latest["bollinger_lower"])) / band_w if band_w else np.nan
        except Exception:
            band_pos = np.nan
        vol = enriched["volume"]
        vm = float(vol.tail(20).mean()) if len(vol) >= 1 else np.nan
        vs = float(vol.tail(20).std()) or 1e-9
        return {
            "mom_20": float(c.iloc[-1] / c.iloc[-21] - 1) if len(c) > 21 else np.nan,
            "mom_5": float(c.iloc[-1] / c.iloc[-6] - 1) if len(c) > 6 else np.nan,
            "rsi": float(latest["rsi"]),
            "macd_hist": float(latest["macd"] - latest["macd_signal"]),
            "ma_dis_20": float(c.iloc[-1] / latest["ma20"] - 1) if latest["ma20"] else np.nan,
            "ma_dis_60": float(c.iloc[-1] / latest["ma60"] - 1) if latest["ma60"] else np.nan,
            "band_pos": float(band_pos),
            "volume_z": float((float(vol.iloc[-1]) - vm) / vs) if not np.isnan(vm) else np.nan,
            "volatility": float(latest["volatility"]),
        }

    def score(self, enriched: pd.DataFrame, horizon_days: int = 5) -> LearnedSignal | None:
        if enriched is None or enriched.empty or len(enriched) < 80:
            return None
        report = self.ic_service.compute(horizon_days=horizon_days, universe_size=40)
        if not report.factors:
            return None

        fvals = self._factor_values(enriched)
        # 모집단 통계: IC 계산 때 쓴 패널이 이상적이나, 여기선 자기 시계열 표준화로 근사
        # (횡단면 모집단 z가 정석이지만 비용 ↓ 위해 시계열 z 사용 → 한계 명시)
        contribs = []
        weighted = 0.0
        wsum = 0.0
        for f in report.factors:
            if abs(f.ic) < _MIN_ABS_IC:
                continue
            v = fvals.get(f.factor)
            if v is None or np.isnan(v):
                continue
            z = self._timeseries_z(enriched, f.factor, v)
            if z is None:
                continue
            z = max(-3, min(3, z))
            # IC 부호 방향으로 z 기여 (IC>0: 값 높을수록 매수 우호)
            contrib = np.sign(f.ic) * z * abs(f.ic)
            weighted += contrib
            wsum += abs(f.ic)
            contribs.append({
                "factor": f.factor, "label": f.label,
                "ic": round(f.ic, 4), "z": round(z, 2),
                "contrib": round(contrib, 4),
            })

        if wsum == 0:
            return LearnedSignal(50.0, "중립", [], 0, "유효 factor 없음 (IC 미달).")

        norm = weighted / wsum  # 대략 -3~3
        score = max(0.0, min(100.0, 50 + norm * 16))  # 스케일링
        label = "매수 우호" if score >= 60 else "매도 우호" if score <= 40 else "중립"
        contribs.sort(key=lambda x: abs(x["contrib"]), reverse=True)
        return LearnedSignal(
            score=score, label=label, contributions=contribs[:6],
            used_factors=len(contribs),
            note=f"IC 가중 합성 ({horizon_days}일 시계, |IC|≥{_MIN_ABS_IC} factor만). 시계열 z 표준화 근사.",
        )

    def _timeseries_z(self, enriched: pd.DataFrame, factor: str, latest_val: float) -> float | None:
        """factor 시계열 분포 기준 최신값 z-score."""
        try:
            c = enriched["close"]
            if factor == "mom_20":
                s = c.pct_change(20)
            elif factor == "mom_5":
                s = c.pct_change(5)
            elif factor == "rsi":
                s = enriched["rsi"]
            elif factor == "macd_hist":
                s = enriched["macd"] - enriched["macd_signal"]
            elif factor == "ma_dis_20":
                s = c / enriched["ma20"] - 1
            elif factor == "ma_dis_60":
                s = c / enriched["ma60"] - 1
            elif factor == "band_pos":
                w = (enriched["bollinger_upper"] - enriched["bollinger_lower"]).replace(0, np.nan)
                s = (c - enriched["bollinger_lower"]) / w
            elif factor == "volume_z":
                vm = enriched["volume"].rolling(20).mean()
                vs = enriched["volume"].rolling(20).std()
                s = (enriched["volume"] - vm) / (vs + 1e-9)
            elif factor == "volatility":
                s = enriched["volatility"]
            else:
                return None
            s = s.replace([np.inf, -np.inf], np.nan).dropna()
            if len(s) < 30:
                return None
            mu, sd = float(s.mean()), float(s.std())
            if sd <= 1e-9:
                return 0.0
            return (latest_val - mu) / sd
        except Exception:
            return None
