"""data_provider 폴백 체인 단위 테스트.

pykrx / FinanceDataReader / yfinance 는 함수 안에서 import 하므로 sys.modules 에
가짜 모듈을 꽂는다. 그러면 컬럼 rename, 정렬, 검증까지 실제 코드 경로를 그대로
타면서도 네트워크는 타지 않는다.
"""
import sys
import types

import numpy as np
import pandas as pd
import pytest

from app.core.config import Settings
from app.services.data_provider import (
    DataProviderError,
    KoreanStockDataProvider,
    StockDataProvider,
    YahooDataProvider,
)


@pytest.fixture(autouse=True)
def pinned_settings(monkeypatch):
    """backend/.env 가 있든 없든 테스트는 같은 설정에서 돈다."""
    monkeypatch.setattr(Settings, "DATA_PROVIDER", "auto")
    monkeypatch.setattr(Settings, "ALLOW_SAMPLE_FALLBACK", False)
    monkeypatch.setattr(Settings, "DATA_CACHE_TTL_SECONDS", 60)
    monkeypatch.setattr(Settings, "LOG_DATA_PROVIDER_ERRORS", True)


@pytest.fixture
def fake_module(monkeypatch):
    def _install(name, **attrs):
        module = types.ModuleType(name)
        for key, value in attrs.items():
            setattr(module, key, value)
        monkeypatch.setitem(sys.modules, name, module)
        return module

    return _install


@pytest.fixture
def kr_providers(fake_module):
    """pykrx 와 FinanceDataReader 를 한 번에 꽂는다."""

    def _install(*, pykrx, fdr):
        fake_module("pykrx", stock=types.SimpleNamespace(get_market_ohlcv_by_date=pykrx))
        fake_module("FinanceDataReader", DataReader=fdr)
        return pykrx, fdr

    return _install


def stub(*, returns=None, raises=None):
    """호출을 기록하는 스텁. returns 가 callable 이면 호출 시점에 값을 만든다."""

    def call(*args, **kwargs):
        call.calls.append((args, kwargs))
        if raises is not None:
            raise raises
        return returns() if callable(returns) else returns

    call.calls = []
    return call


def pykrx_frame(rows=5, ascending=True, drop=None):
    """pykrx 응답 모양 — 한글 컬럼, '날짜' 이름의 DatetimeIndex."""
    frame = pd.DataFrame(
        {
            "시가": np.arange(rows, dtype=float) + 1000,
            "고가": np.arange(rows, dtype=float) + 1100,
            "저가": np.arange(rows, dtype=float) + 900,
            "종가": np.arange(rows, dtype=float) + 1050,
            "거래량": np.arange(rows) + 10_000,
        },
        index=pd.Index(pd.bdate_range("2024-03-01", periods=rows), name="날짜"),
    )
    if drop:
        frame = frame.drop(columns=list(drop))
    return frame if ascending else frame.iloc[::-1]


def fdr_frame(rows=5):
    """FinanceDataReader 응답 모양. Change 는 우리가 쓰지 않는 여분 컬럼."""
    return pd.DataFrame(
        {
            "Open": np.arange(rows, dtype=float) + 2000,
            "High": np.arange(rows, dtype=float) + 2100,
            "Low": np.arange(rows, dtype=float) + 1900,
            "Close": np.arange(rows, dtype=float) + 2050,
            "Volume": np.arange(rows) + 20_000,
            "Change": np.zeros(rows),
        },
        index=pd.Index(pd.bdate_range("2024-03-01", periods=rows), name="Date"),
    )


def yfinance_frame(ticker="AAPL", rows=5):
    """yfinance 는 단일 티커에도 (필드, 티커) MultiIndex 컬럼을 돌려준다."""
    values = np.column_stack(
        [
            np.arange(rows) + 300.0,
            np.arange(rows) + 310.0,
            np.arange(rows) + 290.0,
            np.arange(rows) + 305.0,
            np.arange(rows) + 30_000.0,
        ]
    )
    return pd.DataFrame(
        values,
        index=pd.Index(pd.bdate_range("2024-03-01", periods=rows), name="Date"),
        columns=pd.MultiIndex.from_product(
            [["Open", "High", "Low", "Close", "Volume"], [ticker]],
            names=["Price", "Ticker"],
        ),
    )


# --- 티커 정규화 / 시장 판별 ---------------------------------------------


def test_alias_and_suffix_normalization():
    provider = StockDataProvider()
    assert provider.normalize_ticker("삼성전자") == "005930"
    assert provider.normalize_ticker(" 애플 ") == "AAPL"
    assert provider.normalize_ticker("005930.KS") == "005930"
    assert provider.normalize_ticker("035720.KQ") == "035720"
    assert provider.normalize_ticker("aapl") == "AAPL"


@pytest.mark.parametrize(
    "bad",
    ["005930/../etc", "AAPL?x=1", "AA%20PL", "A#B", "A&B", "AA\\PL", "AA\nPL"],
)
def test_normalize_rejects_injection_characters(bad):
    with pytest.raises(DataProviderError) as excinfo:
        StockDataProvider().normalize_ticker(bad)
    assert excinfo.value.error_type == "invalid_ticker_format"


def test_detect_market():
    provider = StockDataProvider()
    assert provider.detect_market("005930") == "KR"
    assert provider.detect_market("005930.KS") == "KR"
    assert provider.detect_market("AAPL") == "US"
    assert provider.detect_market("BRK.B") == "US"


def test_detect_market_rejects_unknown_format():
    # 별칭에 없는 한글 종목명은 normalize 를 통과하고 여기서 형식 안내로 걸린다.
    with pytest.raises(DataProviderError) as excinfo:
        StockDataProvider().detect_market("없는종목")
    assert excinfo.value.error_type == "invalid_ticker_format"


# --- provider 선택 --------------------------------------------------------


def test_auto_routes_by_market():
    provider = StockDataProvider()
    assert isinstance(provider._select_provider("KR"), KoreanStockDataProvider)
    assert isinstance(provider._select_provider("US"), YahooDataProvider)


def test_explicit_provider_overrides_market(monkeypatch):
    provider = StockDataProvider()
    monkeypatch.setattr(Settings, "DATA_PROVIDER", "yfinance")
    assert isinstance(provider._select_provider("KR"), YahooDataProvider)
    monkeypatch.setattr(Settings, "DATA_PROVIDER", "pykrx")
    assert isinstance(provider._select_provider("US"), KoreanStockDataProvider)


# --- 한국 주식 폴백 체인 --------------------------------------------------


def test_pykrx_failure_falls_back_to_finance_datareader(kr_providers):
    pykrx, fdr = kr_providers(
        pykrx=stub(raises=RuntimeError("KRX 502")),
        fdr=stub(returns=fdr_frame),
    )
    result = StockDataProvider().fetch_ohlcv("005930", "1y")

    assert result.source == "FinanceDataReader"
    assert result.is_sample is False
    assert [item["name"] for item in result.providers_tried] == ["pykrx", "FinanceDataReader"]
    assert result.providers_tried[0]["status"] == "error"
    assert "KRX 502" in result.providers_tried[0]["error"]
    assert result.providers_tried[1]["status"] == "success"
    assert len(pykrx.calls) == 1
    assert len(fdr.calls) == 1


def test_empty_pykrx_frame_is_treated_as_failure(kr_providers):
    kr_providers(
        pykrx=stub(returns=lambda: pykrx_frame(rows=0)),
        fdr=stub(returns=fdr_frame),
    )
    result = StockDataProvider().fetch_ohlcv("005930", "1y")

    assert result.source == "FinanceDataReader"
    assert result.providers_tried[0]["error"] == "empty dataframe"


def test_missing_column_from_pykrx_falls_back(kr_providers):
    kr_providers(
        pykrx=stub(returns=lambda: pykrx_frame(drop=["거래량"])),
        fdr=stub(returns=fdr_frame),
    )
    result = StockDataProvider().fetch_ohlcv("005930", "1y")

    assert result.source == "FinanceDataReader"
    # 컬럼 검증이 잡아야 한다. 그냥 KeyError 로 터져도 폴백은 되지만 이유가 남지 않는다.
    assert result.providers_tried[0]["error"] == "missing columns: ['volume']"


def test_pykrx_success_skips_finance_datareader(kr_providers):
    _, fdr = kr_providers(pykrx=stub(returns=pykrx_frame), fdr=stub(returns=fdr_frame))
    result = StockDataProvider().fetch_ohlcv("005930", "1y")

    assert result.source == "pykrx"
    assert fdr.calls == []


def test_all_kr_providers_failing_raises(kr_providers):
    kr_providers(
        pykrx=stub(raises=RuntimeError("KRX 502")),
        fdr=stub(raises=ValueError("FDR down")),
    )
    with pytest.raises(DataProviderError) as excinfo:
        StockDataProvider().fetch_ohlcv("005930", "1y")

    error = excinfo.value
    assert error.error_type == "all_providers_failed"
    assert error.source == "none"
    assert [item["name"] for item in error.providers_tried] == ["pykrx", "FinanceDataReader"]
    assert "KRX 502" in error.message
    assert "FDR down" in error.message


# --- 응답 정규화 ----------------------------------------------------------


def test_pykrx_columns_are_renamed_and_sorted(kr_providers):
    # 역순으로 온 응답도 날짜 오름차순으로 정렬돼야 한다.
    kr_providers(
        pykrx=stub(returns=lambda: pykrx_frame(rows=4, ascending=False)),
        fdr=stub(returns=fdr_frame),
    )
    data = StockDataProvider().fetch_ohlcv("005930", "1y").data

    assert list(data.columns) == ["date", "open", "high", "low", "close", "volume"]
    assert list(data["date"]) == sorted(data["date"])
    assert data["close"].tolist() == [1050.0, 1051.0, 1052.0, 1053.0]
    assert data["volume"].dtype.kind == "i"


def test_finance_datareader_extra_columns_are_dropped(kr_providers):
    kr_providers(pykrx=stub(raises=RuntimeError("down")), fdr=stub(returns=fdr_frame))
    data = StockDataProvider().fetch_ohlcv("005930", "1y").data

    assert list(data.columns) == ["date", "open", "high", "low", "close", "volume"]
    assert data["close"].iloc[0] == 2050.0


def test_yfinance_multiindex_columns_are_flattened(fake_module):
    fake_module("yfinance", download=stub(returns=lambda: yfinance_frame("AAPL")))
    result = StockDataProvider().fetch_ohlcv("AAPL", "1y")

    assert result.source == "yfinance"
    assert result.market == "US"
    assert list(result.data.columns) == ["date", "open", "high", "low", "close", "volume"]
    assert result.data["close"].iloc[0] == 305.0


def test_yfinance_period_is_mapped(fake_module):
    download = stub(returns=lambda: yfinance_frame("AAPL"))
    fake_module("yfinance", download=download)
    StockDataProvider().fetch_ohlcv("AAPL", "1m")

    assert download.calls[0][1]["period"] == "1mo"


# --- 재시도 --------------------------------------------------------------


def test_network_error_is_retried_once(fake_module):
    download = stub(raises=ConnectionError("timeout"))
    fake_module("yfinance", download=download)

    with pytest.raises(DataProviderError) as excinfo:
        StockDataProvider().fetch_ohlcv("AAPL", "1y")

    assert excinfo.value.error_type == "network_or_api_error"
    assert len(download.calls) == 2


def test_empty_response_is_not_retried(fake_module):
    # 빈 응답은 다시 물어봐도 빈 응답이다. 재시도할 이유가 없다.
    download = stub(returns=lambda: pd.DataFrame())
    fake_module("yfinance", download=download)

    with pytest.raises(DataProviderError) as excinfo:
        StockDataProvider().fetch_ohlcv("AAPL", "1y")

    assert excinfo.value.error_type == "empty_dataframe"
    assert len(download.calls) == 1


# --- 샘플 폴백 -----------------------------------------------------------


def test_sample_fallback_is_off_by_default(fake_module):
    fake_module("yfinance", download=stub(raises=ConnectionError("timeout")))
    with pytest.raises(DataProviderError):
        StockDataProvider().fetch_ohlcv("AAPL", "1y")


def test_sample_fallback_marks_the_result(monkeypatch, fake_module):
    monkeypatch.setattr(Settings, "ALLOW_SAMPLE_FALLBACK", True)
    fake_module("yfinance", download=stub(raises=ConnectionError("timeout")))
    result = StockDataProvider().fetch_ohlcv("AAPL", "1y")

    assert result.is_sample is True
    assert result.source == "sample"
    assert result.provider_status == "fallback"
    assert "timeout" in result.provider_error
    assert [item["name"] for item in result.providers_tried] == ["yfinance", "sample"]
    assert not result.data.empty


# --- 캐시 ----------------------------------------------------------------


def test_second_fetch_uses_the_cache(kr_providers):
    pykrx, _ = kr_providers(pykrx=stub(returns=pykrx_frame), fdr=stub(returns=fdr_frame))
    provider = StockDataProvider()
    provider.fetch_ohlcv("005930", "1y")
    provider.fetch_ohlcv("005930", "1y")

    assert len(pykrx.calls) == 1


def test_force_refresh_bypasses_the_cache(kr_providers):
    pykrx, _ = kr_providers(pykrx=stub(returns=pykrx_frame), fdr=stub(returns=fdr_frame))
    provider = StockDataProvider()
    provider.fetch_ohlcv("005930", "1y")
    provider.fetch_ohlcv("005930", "1y", force_refresh=True)

    assert len(pykrx.calls) == 2


def test_cache_key_separates_periods(kr_providers):
    pykrx, _ = kr_providers(pykrx=stub(returns=pykrx_frame), fdr=stub(returns=fdr_frame))
    provider = StockDataProvider()
    provider.fetch_ohlcv("005930", "1y")
    provider.fetch_ohlcv("005930", "3m")

    assert len(pykrx.calls) == 2


def test_expired_entry_is_refetched(monkeypatch, kr_providers):
    monkeypatch.setattr(Settings, "DATA_CACHE_TTL_SECONDS", 0)
    pykrx, _ = kr_providers(pykrx=stub(returns=pykrx_frame), fdr=stub(returns=fdr_frame))
    provider = StockDataProvider()
    provider.fetch_ohlcv("005930", "1y")
    provider.fetch_ohlcv("005930", "1y")

    assert len(pykrx.calls) == 2


def test_caller_cannot_mutate_the_cached_entry(kr_providers):
    kr_providers(pykrx=stub(returns=pykrx_frame), fdr=stub(returns=fdr_frame))
    provider = StockDataProvider()

    first = provider.fetch_ohlcv("005930", "1y")
    first.data.loc[0, "close"] = -1
    first.providers_tried.clear()

    second = provider.fetch_ohlcv("005930", "1y")
    assert second.data.loc[0, "close"] == 1050.0
    assert second.providers_tried


# --- 호출부에서 쓰는 표면 -------------------------------------------------


def test_get_quote_reports_change_against_previous_close(kr_providers):
    kr_providers(
        pykrx=stub(returns=lambda: pykrx_frame(rows=3)),
        fdr=stub(returns=fdr_frame),
    )
    quote = StockDataProvider().get_quote("005930", "1y")

    assert quote["current_price"] == 1052.0
    assert quote["previous_close"] == 1051.0
    assert quote["change"] == 1.0
    assert quote["change_rate"] == round(1 / 1051 * 100, 2)
    assert quote["source"] == "pykrx"
    assert quote["is_sample"] is False


def test_debug_fetch_reports_the_failure_chain(kr_providers):
    kr_providers(
        pykrx=stub(raises=RuntimeError("KRX 502")),
        fdr=stub(raises=ValueError("FDR down")),
    )
    payload = StockDataProvider().debug_fetch("삼성전자", "1y")

    assert payload["original_ticker"] == "삼성전자"
    assert payload["normalized_ticker"] == "005930"
    assert payload["error_type"] == "all_providers_failed"
    assert [item["name"] for item in payload["providers_tried"]] == ["pykrx", "FinanceDataReader"]
    assert payload["is_sample"] is False
