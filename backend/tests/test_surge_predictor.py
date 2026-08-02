"""Triple Barrier 라벨링 + 누수 검증."""
import numpy as np
import pandas as pd

from app.services.surge_predictor import SurgePredictor, classify_signal


def test_triple_barrier_upper_hit():
    # +10% 먼저 도달 → 라벨 1
    p = SurgePredictor(upper=0.10, lower=-0.05, horizon=10)
    close = pd.Series([100, 101, 103, 106, 111, 112] + [112] * 20)  # day4에 +11%
    labels = p._triple_barrier_label(close)
    assert labels.iloc[0] == 1


def test_triple_barrier_lower_hit():
    # -5% 먼저 도달 → 라벨 0
    p = SurgePredictor(upper=0.10, lower=-0.05, horizon=10)
    close = pd.Series([100, 99, 97, 94, 93] + [93] * 20)  # day3에 -6%
    labels = p._triple_barrier_label(close)
    assert labels.iloc[0] == 0


def test_triple_barrier_no_lookahead():
    # 마지막 horizon개 행은 미래 모름 → NaN
    p = SurgePredictor(horizon=10)
    close = pd.Series(np.linspace(100, 200, 60))
    labels = p._triple_barrier_label(close)
    assert labels.iloc[-10:].isna().all()
    assert labels.iloc[:-10].notna().all()


def test_classify_signal_thresholds():
    assert classify_signal(0.6, 0.2) == "매우 강함"   # prob 0.6, lift 3
    assert classify_signal(0.45, 0.3) == "강함"        # lift 1.5
    assert classify_signal(0.1, 0.3) == "신호 없음"


def test_predict_insufficient_returns_none():
    p = SurgePredictor()
    assert p.predict(pd.DataFrame()) is None
