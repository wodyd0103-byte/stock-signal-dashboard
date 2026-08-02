"""
IC (Information Coefficient) 분석 서비스.

각 factor가 미래 수익률과 실제 상관있는지 수치화 (Alphalens 방식).
- 일자별 횡단면 순위상관(Spearman) = daily IC
- IC = 평균, ICIR = 평균/표준편차 (안정성)
- |IC| > 0.03 쓸만, > 0.05 좋음

한계: price-derived factor만 (full 이력 필요). 외부 factor(수급/뉴스/심리)는
이력 크롤링 비용 때문에 제외. 캐시 6시간.
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from threading import Lock

import numpy as np
import pandas as pd

logger = logging.getLogger("ic")

_cache: dict[tuple, tuple[float, "ICReport"]] = {}
_cache_lock = Lock()
_TTL = 6 * 3600

# factor 정의: enriched 컬럼 → 횡단면 비교 가능한 값
# (factor_key, 설명, 기대 방향)
FACTOR_DEFS = [
    ("mom_20",      "20일 모멘텀",     "+"),
    ("mom_5",       "5일 모멘텀",      "+"),
    ("rsi",         "RSI",             "?"),
    ("macd_hist",   "MACD 히스토그램",  "+"),
    ("ma_dis_20",   "MA20 이격도",      "?"),
    ("ma_dis_60",   "MA60 이격도",      "+"),
    ("band_pos",    "볼린저 위치",      "-"),
    ("volume_z",    "거래량 z-score",   "+"),
    ("volatility",  "변동성(저변동 팩터)", "-"),
]


@dataclass
class FactorIC:
    factor: str
    label: str
    ic: float           # 평균 IC
    icir: float         # IC / std (안정성)
    hit_rate: float     # IC 부호 일관성 (양수 비율)
    n_periods: int
    verdict: str        # "강함" / "보통" / "약함" / "무의미"


@dataclass
class ICReport:
    horizon_days: int
    universe_size: int
    factors: list[FactorIC]
    updated_at: str
    note: str

    def to_dict(self) -> dict:
        return {
            "horizon_days": self.horizon_days,
            "universe_size": self.universe_size,
            "updated_at": self.updated_at,
            "note": self.note,
            "factors": [
                {
                    "factor": f.factor, "label": f.label,
                    "ic": round(f.ic, 4), "icir": round(f.icir, 3),
                    "hit_rate": round(f.hit_rate, 3),
                    "n_periods": f.n_periods, "verdict": f.verdict,
                }
                for f in self.factors
            ],
        }


def _verdict(ic: float, icir: float) -> str:
    a = abs(ic)
    if a >= 0.05 and abs(icir) >= 0.3:
        return "강함"
    if a >= 0.03:
        return "보통"
    if a >= 0.015:
        return "약함"
    return "무의미"


class ICService:
    def __init__(self, data_provider, indicator_service, universe_service):
        self.data_provider = data_provider
        self.indicator_service = indicator_service
        self.universe_service = universe_service

    def compute(self, horizon_days: int = 5, universe_size: int = 40, force: bool = False) -> ICReport:
        key = (horizon_days, universe_size)
        now = time.time()
        if not force:
            with _cache_lock:
                hit = _cache.get(key)
            if hit and (now - hit[0]) < _TTL:
                return hit[1]

        panel = self._build_panel(horizon_days, universe_size)
        if panel is None or panel.empty:
            report = ICReport(horizon_days, 0, [], _now(), "데이터 부족 — IC 계산 불가")
        else:
            report = self._compute_ic(panel, horizon_days, universe_size)

        with _cache_lock:
            _cache[key] = (now, report)
        return report

    def _build_panel(self, horizon: int, universe_size: int) -> pd.DataFrame | None:
        """유니버스 종목 factor + 미래수익률 long 패널 생성."""
        uni = self.universe_service.get_representative_stocks(
            market="KR", kr_limit=universe_size, us_limit=0, source="auto"
        )
        rows = []
        for stock in uni.items[:universe_size]:
            ticker = stock["ticker"]
            try:
                res = self.data_provider.fetch_ohlcv(ticker, "1y")
                enriched = self.indicator_service.enrich(res.data)
            except Exception:
                continue
            if enriched is None or len(enriched) < 80:
                continue
            f = self._factors(enriched)
            # 미래 수익률 (horizon일 후)
            f["fwd_ret"] = enriched["close"].shift(-horizon) / enriched["close"] - 1
            f["date"] = pd.to_datetime(enriched["date"])
            f["ticker"] = ticker
            rows.append(f)
        if not rows:
            return None
        panel = pd.concat(rows, ignore_index=True)
        return panel.dropna(subset=["fwd_ret"])

    def _factors(self, e: pd.DataFrame) -> pd.DataFrame:
        c = e["close"]
        out = pd.DataFrame(index=e.index)
        out["mom_20"] = c.pct_change(20)
        out["mom_5"] = c.pct_change(5)
        out["rsi"] = e["rsi"]
        out["macd_hist"] = e["macd"] - e["macd_signal"]
        out["ma_dis_20"] = c / e["ma20"] - 1
        out["ma_dis_60"] = c / e["ma60"] - 1
        width = (e["bollinger_upper"] - e["bollinger_lower"]).replace(0, np.nan)
        out["band_pos"] = (c - e["bollinger_lower"]) / width
        vm = e["volume"].rolling(20).mean()
        vs = e["volume"].rolling(20).std()
        out["volume_z"] = (e["volume"] - vm) / (vs + 1e-9)
        out["volatility"] = e["volatility"]
        return out.replace([np.inf, -np.inf], np.nan)

    def _compute_ic(self, panel: pd.DataFrame, horizon: int, universe_size: int) -> ICReport:
        factor_cols = [f[0] for f in FACTOR_DEFS]
        labels = {f[0]: f[1] for f in FACTOR_DEFS}

        results: list[FactorIC] = []
        for col in factor_cols:
            sub = panel[["date", col, "fwd_ret"]].dropna()
            if sub.empty:
                continue
            # 일자별 횡단면 Spearman IC (종목 ≥5 인 날짜만)
            daily_ic = []
            for _, g in sub.groupby("date"):
                if len(g) < 5:
                    continue
                ic = g[col].corr(g["fwd_ret"], method="spearman")
                if pd.notna(ic):
                    daily_ic.append(ic)
            if len(daily_ic) < 10:
                continue
            arr = np.array(daily_ic)
            ic_mean = float(arr.mean())
            ic_std = float(arr.std()) or 1e-9
            icir = ic_mean / ic_std
            hit = float((np.sign(arr) == np.sign(ic_mean)).mean())
            results.append(FactorIC(
                factor=col, label=labels[col],
                ic=ic_mean, icir=icir, hit_rate=hit,
                n_periods=len(daily_ic), verdict=_verdict(ic_mean, icir),
            ))

        # |IC| 내림차순
        results.sort(key=lambda x: abs(x.ic), reverse=True)
        note = (
            f"일자별 횡단면 Spearman IC 평균. |IC|>0.05 강함, >0.03 보통. "
            f"price-derived factor만 (외부 factor 제외)."
        )
        return ICReport(horizon, universe_size, results, _now(), note)


def _now() -> str:
    from datetime import datetime
    return datetime.now().isoformat(timespec="seconds")
