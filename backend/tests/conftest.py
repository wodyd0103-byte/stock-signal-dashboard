"""테스트 공통 fixture — 네트워크 없이 합성 OHLCV/enriched 생성."""
import numpy as np
import pandas as pd
import pytest

from app.services.indicator_service import IndicatorService


def make_ohlcv(n=260, seed=0, trend=0.0, start=10000.0):
    """합성 일봉. trend>0 상승추세."""
    rng = np.random.default_rng(seed)
    steps = rng.normal(trend, 1.0, n).cumsum()
    close = np.maximum(start + steps * 50, 100)
    dates = pd.date_range("2024-01-01", periods=n, freq="B")
    df = pd.DataFrame({
        "date": dates,
        "open": close + rng.normal(0, 5, n),
        "high": close + np.abs(rng.normal(0, 20, n)),
        "low": close - np.abs(rng.normal(0, 20, n)),
        "close": close,
        "volume": np.abs(rng.normal(1_000_000, 100_000, n)).astype(int),
    })
    df["high"] = df[["high", "close", "open"]].max(axis=1)
    df["low"] = df[["low", "close", "open"]].min(axis=1)
    return df


@pytest.fixture
def enriched():
    return IndicatorService().enrich(make_ohlcv())


@pytest.fixture
def enriched_uptrend():
    return IndicatorService().enrich(make_ohlcv(trend=0.5, seed=1))
