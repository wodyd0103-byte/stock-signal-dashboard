"""
급등주 예측 서비스.

방법론:
- Triple Barrier 라벨링 (Lopez de Prado): 상단 / 하단 / 시간만료 중 첫 도달
- 분류기: GradientBoosting (sklearn 기존 의존성)
- Walk-forward CV (TimeSeriesSplit) 로 AUC 측정
- 클래스 불균형: sample_weight 자동 (positive 비율 역수)

학계 참고:
- Triple Barrier (Lopez de Prado, Advances in Financial ML)
- Sungwoo Kang (2025) "Stock Price Prediction Using Triple Barrier Labeling and Raw OHLCV Data: Evidence from Korean Markets"
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import TimeSeriesSplit


# 라벨 파라미터 (Sungwoo Kang 2025 기준 + 한국시장 보정)
DEFAULT_UPPER = 0.10     # +10% 도달 = 급등
DEFAULT_LOWER = -0.05    # -5% 도달 = 손절 (보수)
DEFAULT_HORIZON = 10     # 10 거래일 (~2주)

SURGE_FEATURES = [
    "ret1", "ret5", "ret20",
    "vol20", "rsi", "macd",
    "ma_dis_5", "ma_dis_20", "ma_dis_60",
    "volume_z", "volume_chg5",
    "hl_range", "hl_range_5",
]

WALK_FORWARD_SPLITS = 4
WALK_FORWARD_MIN_ROWS = 80


@dataclass
class SurgePrediction:
    surge_probability: float
    base_rate: float
    lift: float
    cv_score: float
    train_samples: int
    train_positive: int
    upper_pct: float
    horizon_days: int
    reasons: list[str]


class SurgePredictor:
    def __init__(
        self,
        upper: float = DEFAULT_UPPER,
        lower: float = DEFAULT_LOWER,
        horizon: int = DEFAULT_HORIZON,
    ):
        self.upper = upper
        self.lower = lower
        self.horizon = horizon

    def predict(self, enriched: pd.DataFrame) -> SurgePrediction | None:
        """단일 종목 급등 확률 예측."""
        if enriched is None or enriched.empty:
            return None

        features = self._build_features(enriched)
        labels = self._triple_barrier_label(enriched["close"])
        df = features.copy()
        df["target"] = labels
        df = df.dropna(subset=SURGE_FEATURES + ["target"])

        if len(df) < WALK_FORWARD_MIN_ROWS + 20:
            return None

        # 마지막 horizon 만큼은 미래 알 수 없음 → 학습 제외
        train = df.iloc[: -self.horizon].copy()
        latest = df.iloc[[-1]]  # 최신 시점 (예측 대상)

        if train["target"].sum() < 5:
            # 양성 샘플 너무 적음 → 모델 신뢰 X
            base_rate = float(train["target"].mean()) if len(train) else 0.0
            return SurgePrediction(
                surge_probability=base_rate,
                base_rate=base_rate,
                lift=1.0,
                cv_score=0.5,
                train_samples=int(len(train)),
                train_positive=int(train["target"].sum()),
                upper_pct=self.upper * 100,
                horizon_days=self.horizon,
                reasons=["과거 급등 사례 부족 - 기저 비율 반환"],
            )

        X = train[SURGE_FEATURES]
        y = train["target"].astype(int)

        # Walk-forward AUC
        cv_score = self._walk_forward_auc(X, y)

        # 최종 모델 (전체 train)
        sample_weight = self._balanced_weights(y)
        model = GradientBoostingClassifier(
            n_estimators=150,
            max_depth=4,
            learning_rate=0.05,
            subsample=0.8,
            random_state=42,
        )
        model.fit(X, y, sample_weight=sample_weight)

        x_latest = latest[SURGE_FEATURES]
        prob = float(model.predict_proba(x_latest)[0, 1])
        base_rate = float(y.mean())
        lift = prob / base_rate if base_rate > 1e-6 else 0.0

        # 자연어 근거 (피처 중요도 상위)
        importance = pd.Series(model.feature_importances_, index=SURGE_FEATURES)
        top_features = importance.nlargest(3).index.tolist()
        latest_vals = latest[SURGE_FEATURES].iloc[0]
        reasons = self._build_reasons(top_features, latest_vals, prob, base_rate)

        return SurgePrediction(
            surge_probability=prob,
            base_rate=base_rate,
            lift=lift,
            cv_score=cv_score,
            train_samples=int(len(train)),
            train_positive=int(y.sum()),
            upper_pct=self.upper * 100,
            horizon_days=self.horizon,
            reasons=reasons,
        )

    # ─── 피처 ────────────────────────────────────────────────
    def _build_features(self, enriched: pd.DataFrame) -> pd.DataFrame:
        """indicator_service.enrich 산출물 활용 + 추가 피처."""
        df = enriched.copy()

        # 기존 enriched 컬럼 → 이름 통일
        if "return_1d" in df.columns:
            df["ret1"] = df["return_1d"]
        if "return_5d" in df.columns:
            df["ret5"] = df["return_5d"]
        if "volatility" in df.columns:
            df["vol20"] = df["volatility"]

        c = df["close"]
        df["ret20"] = c.pct_change(20)

        for w in (5, 20, 60):
            col = f"ma{w}" if f"ma{w}" in df.columns else None
            if col:
                df[f"ma_dis_{w}"] = c / df[col] - 1
            else:
                df[f"ma_dis_{w}"] = c / c.rolling(w).mean() - 1

        # 거래량 z-score + 5일 변화
        if "volume" in df.columns:
            vm = df["volume"].rolling(20).mean()
            vs = df["volume"].rolling(20).std()
            df["volume_z"] = (df["volume"] - vm) / (vs + 1e-9)
            df["volume_chg5"] = df["volume"].pct_change(5)
        else:
            df["volume_z"] = 0.0
            df["volume_chg5"] = 0.0

        # 고저 변동성
        if "high" in df.columns and "low" in df.columns:
            df["hl_range"] = (df["high"] - df["low"]) / df["close"]
            df["hl_range_5"] = df["hl_range"].rolling(5).mean()
        else:
            df["hl_range"] = 0.0
            df["hl_range_5"] = 0.0

        return df.replace([np.inf, -np.inf], np.nan)

    # ─── Triple Barrier ──────────────────────────────────────
    def _triple_barrier_label(self, close: pd.Series) -> pd.Series:
        """
        각 시점 t 에서 [t+1, t+horizon] 구간을 보고:
          - 종가가 먼저 +upper 도달  → 1 (급등)
          - 종가가 먼저 -|lower| 도달 → 0 (손절)
          - 시간만료                  → 0 (그냥 미달)
        """
        n = len(close)
        labels = np.zeros(n, dtype=np.int8)
        vals = close.values
        for i in range(n - self.horizon):
            base = vals[i]
            if base <= 0:
                continue
            window = vals[i + 1 : i + 1 + self.horizon] / base - 1
            hit_up_idx = np.argmax(window >= self.upper) if (window >= self.upper).any() else None
            hit_dn_idx = np.argmax(window <= self.lower) if (window <= self.lower).any() else None
            if hit_up_idx is not None:
                if hit_dn_idx is None or hit_up_idx < hit_dn_idx:
                    labels[i] = 1
        # 마지막 horizon은 미정 → NaN
        result = pd.Series(labels.astype(float), index=close.index)
        result.iloc[-self.horizon :] = np.nan
        return result

    # ─── 보조 ────────────────────────────────────────────────
    def _balanced_weights(self, y: pd.Series) -> np.ndarray:
        pos = float(y.sum())
        neg = float(len(y) - pos)
        if pos == 0 or neg == 0:
            return np.ones(len(y))
        w_pos = len(y) / (2 * pos)
        w_neg = len(y) / (2 * neg)
        return np.where(y == 1, w_pos, w_neg)

    def _walk_forward_auc(self, X: pd.DataFrame, y: pd.Series) -> float:
        n = len(X)
        if n < WALK_FORWARD_MIN_ROWS:
            return 0.5
        n_splits = min(WALK_FORWARD_SPLITS, max(2, (n - WALK_FORWARD_MIN_ROWS) // 30))
        # Triple Barrier 라벨이 horizon 일 미래를 참조 → embargo로 누수 차단 (purged CV).
        # fold가 비지 않도록 test 크기-1로 상한.
        test_size = n // (n_splits + 1)
        embargo = max(1, min(self.horizon, max(1, test_size - 1)))
        try:
            tscv = TimeSeriesSplit(n_splits=n_splits, gap=embargo)
        except TypeError:
            tscv = TimeSeriesSplit(n_splits=n_splits)

        aucs: list[float] = []
        for tr_idx, te_idx in tscv.split(X):
            if len(tr_idx) < 30 or len(te_idx) < 5:
                continue
            y_tr = y.iloc[tr_idx]
            if y_tr.sum() < 2 or (len(y_tr) - y_tr.sum()) < 2:
                continue
            model = GradientBoostingClassifier(
                n_estimators=100, max_depth=3, learning_rate=0.05, random_state=42
            )
            sw = self._balanced_weights(y_tr)
            model.fit(X.iloc[tr_idx], y_tr, sample_weight=sw)
            proba = model.predict_proba(X.iloc[te_idx])[:, 1]
            y_te = y.iloc[te_idx]
            if len(set(y_te)) < 2:
                continue
            try:
                aucs.append(float(roc_auc_score(y_te, proba)))
            except Exception:
                continue
        return float(np.mean(aucs)) if aucs else 0.5

    def _build_reasons(
        self,
        top_features: list[str],
        latest: pd.Series,
        prob: float,
        base_rate: float,
    ) -> list[str]:
        reasons: list[str] = []
        explain_map = {
            "ret1":       lambda v: f"전일 수익률 {v*100:+.2f}%",
            "ret5":       lambda v: f"5일 수익률 {v*100:+.2f}%",
            "ret20":      lambda v: f"20일 수익률 {v*100:+.2f}%",
            "vol20":      lambda v: f"변동성 {v*100:.2f}% (20일)",
            "rsi":        lambda v: f"RSI {v:.1f}",
            "macd":       lambda v: f"MACD {v:.3f}",
            "ma_dis_5":   lambda v: f"MA5 이격도 {v*100:+.2f}%",
            "ma_dis_20":  lambda v: f"MA20 이격도 {v*100:+.2f}%",
            "ma_dis_60":  lambda v: f"MA60 이격도 {v*100:+.2f}%",
            "volume_z":   lambda v: f"거래량 z-score {v:+.2f}",
            "volume_chg5": lambda v: f"5일 거래량 변화 {v*100:+.1f}%",
            "hl_range":   lambda v: f"일중 변동폭 {v*100:.2f}%",
            "hl_range_5": lambda v: f"5일 평균 변동폭 {v*100:.2f}%",
        }
        for f in top_features:
            v = latest.get(f, 0.0)
            try:
                reasons.append(explain_map[f](float(v)))
            except Exception:
                continue
        lift = prob / base_rate if base_rate > 1e-6 else 0.0
        reasons.append(f"기저 급등률 {base_rate*100:.1f}% 대비 lift {lift:.2f}배")
        return reasons


def classify_signal(prob: float, base_rate: float) -> str:
    """확률 + 기저 비율 → 자연어 라벨."""
    lift = prob / base_rate if base_rate > 1e-6 else 0.0
    if prob >= 0.55 and lift >= 2.0:
        return "매우 강함"
    if prob >= 0.4 and lift >= 1.5:
        return "강함"
    if prob >= 0.3 and lift >= 1.2:
        return "보통"
    if prob >= 0.2:
        return "약함"
    return "신호 없음"
