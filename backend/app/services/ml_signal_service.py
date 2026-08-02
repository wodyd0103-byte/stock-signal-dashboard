from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score


FEATURE_COLUMNS = [
    "return_1d",
    "return_3d",
    "return_5d",
    "return_20d",
    "volume_ratio_20d",
    "ma5_ma20_ratio",
    "ma20_ma60_ratio",
    "price_ma20_ratio",
    "rsi",
    "macd_histogram",
    "bollinger_percent_b",
    "bollinger_bandwidth",
    "atr",
    "volatility_20d",
    "relative_strength_20d",
]


@dataclass(frozen=True)
class MLSignalResult:
    ml_up_probability: float | None
    ml_signal: str
    model_name: str
    model_confidence: float | None
    feature_importance: list[dict[str, float]]
    provider_error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "ml_up_probability": self.ml_up_probability,
            "ml_signal": self.ml_signal,
            "model_name": self.model_name,
            "model_confidence": self.model_confidence,
            "feature_importance": self.feature_importance,
            "provider_error": self.provider_error,
        }


class MLSignalService:
    """Classifies whether a stock may be up more than 2% after 5 trading days."""

    def predict_up_probability(self, enriched: pd.DataFrame, relative_strength_20d: float | None = None) -> MLSignalResult:
        if enriched.empty or len(enriched) < 90:
            return MLSignalResult(None, "INSUFFICIENT_DATA", "RandomForestClassifier", None, [], "학습 데이터가 부족합니다.")

        try:
            features = self._feature_frame(enriched, relative_strength_20d)
            model_df = features.copy()
            model_df["target"] = ((model_df["close"].shift(-5) / model_df["close"] - 1) >= 0.02).astype(int)
            model_df = model_df.dropna(subset=FEATURE_COLUMNS + ["target"]).reset_index(drop=True)
            model_df = model_df.iloc[:-5] if len(model_df) > 5 else model_df

            if len(model_df) < 70 or model_df["target"].nunique() < 2:
                return MLSignalResult(None, "INSUFFICIENT_CLASSES", "RandomForestClassifier", None, [], "상승/비상승 학습 클래스가 충분하지 않습니다.")

            split_index = max(20, int(len(model_df) * 0.8))
            train = model_df.iloc[:split_index]
            test = model_df.iloc[split_index:]
            if test.empty:
                return MLSignalResult(None, "INSUFFICIENT_TEST_DATA", "RandomForestClassifier", None, [], "검증 데이터가 부족합니다.")

            model = RandomForestClassifier(
                n_estimators=120,
                max_depth=6,
                min_samples_leaf=4,
                random_state=42,
                class_weight="balanced_subsample",
            )
            model.fit(train[FEATURE_COLUMNS], train["target"])
            confidence = float(accuracy_score(test["target"], model.predict(test[FEATURE_COLUMNS])))
            latest_features = features[FEATURE_COLUMNS].dropna().tail(1)
            if latest_features.empty:
                return MLSignalResult(None, "NO_LATEST_FEATURES", "RandomForestClassifier", None, [], "최신 피처를 계산하지 못했습니다.")

            probability = float(model.predict_proba(latest_features)[0][1])
            signal = "UP_PROBABLE" if probability >= 0.6 else "NEUTRAL"
            importance = sorted(
                [
                    {"feature": feature, "importance": round(float(value), 4)}
                    for feature, value in zip(FEATURE_COLUMNS, model.feature_importances_)
                ],
                key=lambda item: item["importance"],
                reverse=True,
            )[:5]
            return MLSignalResult(round(probability, 4), signal, "RandomForestClassifier", round(confidence, 4), importance)
        except Exception as exc:
            return MLSignalResult(None, "MODEL_ERROR", "RandomForestClassifier", None, [], f"{type(exc).__name__}: {exc}")

    def _feature_frame(self, enriched: pd.DataFrame, relative_strength_20d: float | None) -> pd.DataFrame:
        frame = enriched.copy().sort_values("date").reset_index(drop=True)
        close = pd.to_numeric(frame["close"], errors="coerce")
        high = pd.to_numeric(frame["high"], errors="coerce")
        low = pd.to_numeric(frame["low"], errors="coerce")
        volume = pd.to_numeric(frame["volume"], errors="coerce")

        frame["return_3d"] = close.pct_change(3) * 100
        frame["return_20d"] = close.pct_change(20) * 100
        frame["volume_ratio_20d"] = volume / volume.rolling(20, min_periods=5).mean().replace(0, np.nan)
        frame["ma5_ma20_ratio"] = frame["ma5"] / frame["ma20"].replace(0, np.nan)
        frame["ma20_ma60_ratio"] = frame["ma20"] / frame["ma60"].replace(0, np.nan)
        frame["price_ma20_ratio"] = close / frame["ma20"].replace(0, np.nan)
        frame["macd_histogram"] = frame["macd"] - frame["macd_signal"]
        band_width = (frame["bollinger_upper"] - frame["bollinger_lower"]).replace(0, np.nan)
        frame["bollinger_percent_b"] = (close - frame["bollinger_lower"]) / band_width
        frame["bollinger_bandwidth"] = band_width / close.replace(0, np.nan)
        true_range = pd.concat(
            [
                (high - low).abs(),
                (high - close.shift(1)).abs(),
                (low - close.shift(1)).abs(),
            ],
            axis=1,
        ).max(axis=1)
        frame["atr"] = true_range.rolling(14, min_periods=5).mean()
        frame["volatility_20d"] = frame["return_1d"].rolling(20, min_periods=5).std()
        frame["relative_strength_20d"] = float(relative_strength_20d) if relative_strength_20d is not None else frame["return_20d"]
        return frame.replace([np.inf, -np.inf], np.nan)
