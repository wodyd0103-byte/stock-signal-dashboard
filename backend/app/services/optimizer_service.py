"""
Markowitz 포트폴리오 최적화.

보유 종목 가격 이력 → 기대수익(연율) + 공분산 → 최적 비중.
- max_sharpe: 샤프 최대화
- min_variance: 분산 최소화
제약: 비중 합 1, 0<=w<=max_weight (롱온리). scipy SLSQP. 실패 시 균등비중 fallback.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy.optimize import minimize

try:
    from sklearn.covariance import LedoitWolf
    _HAS_LW = True
except Exception:  # pragma: no cover - sklearn 항상 설치돼 있으나 방어
    _HAS_LW = False

logger = logging.getLogger("optimizer")

TRADING_DAYS = 252
RISK_FREE = 0.03


@dataclass
class OptimizeResult:
    method: str
    weights: dict
    exp_return: float
    exp_vol: float
    sharpe: float
    note: str

    def to_dict(self) -> dict:
        return {
            "method": self.method,
            "weights": {k: round(v, 4) for k, v in self.weights.items()},
            "exp_return": round(self.exp_return, 2),
            "exp_vol": round(self.exp_vol, 2),
            "sharpe": round(self.sharpe, 3),
            "note": self.note,
        }


class OptimizerService:
    def __init__(self, data_provider):
        self.data_provider = data_provider

    @staticmethod
    def _covariance(R: pd.DataFrame) -> tuple[np.ndarray, bool]:
        """Ledoit-Wolf 수축 공분산. 종목 수 대비 표본 부족 시 추정오차 축소.

        실패 시 표본 공분산 fallback. (cov_daily, shrunk_flag) 반환.
        """
        if _HAS_LW and len(R) >= len(R.columns):
            try:
                lw = LedoitWolf().fit(R.values)
                return np.asarray(lw.covariance_, dtype=float), True
            except Exception as exc:  # pragma: no cover
                logger.warning(f"Ledoit-Wolf 실패 → 표본 공분산: {exc}")
        return R.cov().values, False

    def optimize(self, tickers: list[str], method: str = "max_sharpe", max_weight: float = 0.4) -> OptimizeResult | None:
        tickers = list(dict.fromkeys(tickers))
        if len(tickers) < 2:
            return None

        rets = {}
        for t in tickers:
            try:
                df = self.data_provider.fetch_ohlcv(t, "1y").data
                if df is None or len(df) < 60:
                    continue
                rets[t] = df.set_index("date")["close"].astype(float).pct_change().dropna()
            except Exception:
                continue
        if len(rets) < 2:
            return None

        R = pd.DataFrame(rets).dropna()
        if len(R) < 40:
            return None
        used = list(R.columns)
        mu = R.mean().values * TRADING_DAYS
        cov, shrunk = self._covariance(R)
        cov = cov * TRADING_DAYS
        n = len(used)
        eff_cap = max(max_weight, 1.0 / n)

        def stats(w):
            r = float(w @ mu)
            v = float(np.sqrt(max(w @ cov @ w, 1e-12)))
            return r, v

        def neg_sharpe(w):
            r, v = stats(w)
            return -(r - RISK_FREE) / v if v > 1e-9 else 1e9

        def variance(w):
            return float(w @ cov @ w)

        cons = [{"type": "eq", "fun": lambda w: float(np.sum(w) - 1)}]
        bounds = [(0.0, eff_cap)] * n
        w0 = np.repeat(1.0 / n, n)
        obj = neg_sharpe if method == "max_sharpe" else variance

        try:
            res = minimize(obj, w0, method="SLSQP", bounds=bounds, constraints=cons,
                           options={"maxiter": 300, "ftol": 1e-9})
            w = res.x if res.success else w0
        except Exception as exc:
            logger.warning(f"최적화 실패 → 균등비중: {exc}")
            w = w0

        w = np.clip(np.asarray(w, dtype=float), 0, None)
        w = w / w.sum() if w.sum() > 0 else w0
        r, v = stats(w)
        sharpe = (r - RISK_FREE) / v if v > 1e-9 else 0.0
        return OptimizeResult(
            method=method,
            weights={used[i]: float(w[i]) for i in range(n)},
            exp_return=r * 100, exp_vol=v * 100, sharpe=sharpe,
            note=(
                f"최근 1년 일수익률 기반 {('최대 샤프' if method == 'max_sharpe' else '최소 분산')} 최적화"
                f"{' · Ledoit-Wolf 수축 공분산' if shrunk else ''}. 과거≠미래, 참고용."
            ),
        )
