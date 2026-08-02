from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
import hashlib
import logging
import math
import re
from threading import Lock
from typing import Any, Literal

import numpy as np
import pandas as pd

from app.core.config import get_settings


Market = Literal["KR", "US"]
COMMON_COLUMNS = ["date", "open", "high", "low", "close", "volume"]

PERIOD_TO_DAYS: dict[str, int] = {
    "1m": 31,
    "1mo": 31,
    "3m": 93,
    "3mo": 93,
    "6m": 186,
    "6mo": 186,
    "1y": 365,
    "3y": 1095,
}

YFINANCE_PERIODS: dict[str, str] = {
    "1m": "1mo",
    "1mo": "1mo",
    "3m": "3mo",
    "3mo": "3mo",
    "6m": "6mo",
    "6mo": "6mo",
    "1y": "1y",
    "3y": "3y",
}

TICKER_ALIASES: dict[str, str] = {
    "삼성전자": "005930",
    "삼성": "005930",
    "SK하이닉스": "000660",
    "하이닉스": "000660",
    "카카오": "035720",
    "네이버": "035420",
    "NAVER": "035420",
    "현대차": "005380",
    "LG에너지솔루션": "373220",
    "애플": "AAPL",
    "마이크로소프트": "MSFT",
    "엔비디아": "NVDA",
    "테슬라": "TSLA",
    "아마존": "AMZN",
    "구글": "GOOGL",
    "알파벳": "GOOGL",
    "메타": "META",
}

logger = logging.getLogger("app.services.data_provider")


@dataclass
class PriceDataResult:
    ticker: str
    market: Market
    source: str
    is_sample: bool
    provider_status: str
    provider_message: str
    data: pd.DataFrame
    provider_error: str | None = None
    selected_provider: str | None = None
    providers_tried: list[dict[str, Any]] = field(default_factory=list)

    def metadata(self) -> dict[str, Any]:
        return {
            "market": self.market,
            "source": self.source,
            "is_sample": self.is_sample,
            "provider_status": self.provider_status,
            "provider_message": self.provider_message,
            "provider_error": self.provider_error,
        }

    def debug_payload(self, original_ticker: str) -> dict[str, Any]:
        return {
            "ticker": original_ticker,
            "normalized_ticker": self.ticker,
            "market": self.market,
            "selected_provider": self.selected_provider,
            "providers_tried": self.providers_tried,
            "final_source": self.source,
            "is_sample": self.is_sample,
            "provider_status": self.provider_status,
            "provider_message": self.provider_message,
            "provider_error": self.provider_error,
        }


class DataProviderError(Exception):
    def __init__(
        self,
        message: str,
        *,
        ticker: str,
        market: Market | str,
        selected_provider: str | None,
        source: str = "none",
        error_type: str = "provider_error",
        providers_tried: list[dict[str, Any]] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.ticker = ticker
        self.market = market
        self.selected_provider = selected_provider
        self.source = source
        self.error_type = error_type
        self.providers_tried = providers_tried or []

    def to_payload(self, original_ticker: str | None = None) -> dict[str, Any]:
        return {
            "ticker": self.ticker,
            "normalized_ticker": self.ticker,
            "original_ticker": original_ticker,
            "market": self.market,
            "selected_provider": self.selected_provider,
            "providers_tried": self.providers_tried,
            "final_source": self.source,
            "source": self.source,
            "is_sample": False,
            "provider_status": "error",
            "provider_message": "실제 데이터를 가져오지 못했습니다.",
            "provider_error": self.message,
            "error_type": self.error_type,
        }


class BaseMarketDataProvider:
    name: str = "base"

    def fetch_ohlcv(self, ticker: str, period: str) -> PriceDataResult:
        raise NotImplementedError

    def _validate_frame(self, df: pd.DataFrame, *, ticker: str, market: Market, source: str) -> pd.DataFrame:
        missing = [column for column in COMMON_COLUMNS if column not in df.columns]
        if missing:
            raise DataProviderError(
                f"{source} 응답에 필수 컬럼이 없습니다: {', '.join(missing)}",
                ticker=ticker,
                market=market,
                selected_provider=self.__class__.__name__,
                source=source,
                error_type="missing_columns",
                providers_tried=[{"name": source, "status": "error", "error": f"missing columns: {missing}"}],
            )

        normalized = df[COMMON_COLUMNS].copy()
        normalized["date"] = pd.to_datetime(normalized["date"]).dt.date
        for column in ["open", "high", "low", "close"]:
            normalized[column] = pd.to_numeric(normalized[column], errors="coerce")
        normalized["volume"] = pd.to_numeric(normalized["volume"], errors="coerce").fillna(0).astype(int)
        normalized = normalized.dropna(subset=["open", "high", "low", "close"])
        normalized = normalized.sort_values("date").reset_index(drop=True)
        if normalized.empty:
            raise DataProviderError(
                f"{source}가 빈 데이터프레임을 반환했습니다. 티커가 잘못되었거나 해당 기간 데이터가 없을 수 있습니다.",
                ticker=ticker,
                market=market,
                selected_provider=self.__class__.__name__,
                source=source,
                error_type="empty_dataframe",
                providers_tried=[{"name": source, "status": "error", "error": "empty dataframe"}],
            )
        return normalized

    def _success_try(self, name: str, df: pd.DataFrame) -> dict[str, Any]:
        return {
            "name": name,
            "status": "success",
            "rows": int(len(df)),
            "start_date": str(df["date"].iloc[0]),
            "end_date": str(df["date"].iloc[-1]),
        }


class YahooDataProvider(BaseMarketDataProvider):
    name = "yfinance"

    def fetch_ohlcv(self, ticker: str, period: str) -> PriceDataResult:
        providers_tried: list[dict[str, Any]] = []
        try:
            import yfinance as yf

            raw = yf.download(
                ticker,
                period=YFINANCE_PERIODS.get(period, period),
                interval="1d",
                progress=False,
                auto_adjust=False,
                threads=False,
                timeout=get_settings().DATA_PROVIDER_TIMEOUT_SECONDS,
            )
        except Exception as exc:
            message = f"yfinance 네트워크 또는 API 오류: {type(exc).__name__}: {exc}"
            providers_tried.append({"name": "yfinance", "status": "error", "error": message})
            raise DataProviderError(
                message,
                ticker=ticker,
                market="US",
                selected_provider=self.__class__.__name__,
                source="yfinance",
                error_type="network_or_api_error",
                providers_tried=providers_tried,
            ) from exc

        try:
            df = self._normalize_yfinance_frame(raw, ticker)
            providers_tried.append(self._success_try("yfinance", df))
            return PriceDataResult(
                ticker=ticker,
                market="US",
                source="yfinance",
                is_sample=False,
                provider_status="success",
                provider_message="실제 데이터를 정상 조회했습니다.",
                data=df,
                selected_provider=self.__class__.__name__,
                providers_tried=providers_tried,
            )
        except DataProviderError as exc:
            if not exc.providers_tried:
                exc.providers_tried = providers_tried
            raise

    def _normalize_yfinance_frame(self, raw: pd.DataFrame, ticker: str) -> pd.DataFrame:
        if raw.empty:
            raise DataProviderError(
                "yfinance가 빈 데이터프레임을 반환했습니다. 티커가 잘못되었거나 해당 기간 데이터가 없습니다.",
                ticker=ticker,
                market="US",
                selected_provider=self.__class__.__name__,
                source="yfinance",
                error_type="empty_dataframe",
                providers_tried=[{"name": "yfinance", "status": "error", "error": "empty dataframe"}],
            )

        frame = raw.copy()
        if isinstance(frame.columns, pd.MultiIndex):
            ticker_level = frame.columns.get_level_values(-1)
            if ticker in ticker_level:
                frame = frame.xs(ticker, axis=1, level=-1, drop_level=True)
            else:
                frame.columns = frame.columns.get_level_values(0)

        frame = frame.reset_index()
        date_col = "Date" if "Date" in frame.columns else "Datetime"
        frame = frame.rename(
            columns={
                date_col: "date",
                "Open": "open",
                "High": "high",
                "Low": "low",
                "Close": "close",
                "Volume": "volume",
            }
        )
        return self._validate_frame(frame, ticker=ticker, market="US", source="yfinance")


class KoreanStockDataProvider(BaseMarketDataProvider):
    name = "pykrx"

    def fetch_ohlcv(self, ticker: str, period: str) -> PriceDataResult:
        start_date, end_date = self._date_range(period)
        providers_tried: list[dict[str, Any]] = []

        try:
            df = self._fetch_pykrx(ticker, start_date, end_date)
            providers_tried.append(self._success_try("pykrx", df))
            return PriceDataResult(
                ticker=ticker,
                market="KR",
                source="pykrx",
                is_sample=False,
                provider_status="success",
                provider_message="실제 데이터를 정상 조회했습니다.",
                data=df,
                selected_provider=self.__class__.__name__,
                providers_tried=providers_tried,
            )
        except DataProviderError as exc:
            providers_tried.extend(exc.providers_tried)
        except Exception as exc:
            providers_tried.append({"name": "pykrx", "status": "error", "error": f"{type(exc).__name__}: {exc}"})

        try:
            df = self._fetch_finance_datareader(ticker, start_date, end_date)
            providers_tried.append(self._success_try("FinanceDataReader", df))
            return PriceDataResult(
                ticker=ticker,
                market="KR",
                source="FinanceDataReader",
                is_sample=False,
                provider_status="success",
                provider_message="실제 데이터를 정상 조회했습니다.",
                data=df,
                selected_provider=self.__class__.__name__,
                providers_tried=providers_tried,
            )
        except DataProviderError as exc:
            providers_tried.extend(exc.providers_tried)
        except Exception as exc:
            providers_tried.append({"name": "FinanceDataReader", "status": "error", "error": f"{type(exc).__name__}: {exc}"})

        message = "; ".join(f"{item['name']}: {item.get('error', item['status'])}" for item in providers_tried)
        raise DataProviderError(
            message or "한국 주식 데이터 제공자가 데이터를 반환하지 않았습니다.",
            ticker=ticker,
            market="KR",
            selected_provider=self.__class__.__name__,
            source="none",
            error_type="all_providers_failed",
            providers_tried=providers_tried,
        )

    def _date_range(self, period: str) -> tuple[date, date]:
        end_date = datetime.utcnow().date()
        start_date = end_date - timedelta(days=PERIOD_TO_DAYS.get(period, 365))
        return start_date, end_date

    def _fetch_pykrx(self, ticker: str, start_date: date, end_date: date) -> pd.DataFrame:
        from pykrx import stock

        raw = stock.get_market_ohlcv_by_date(
            start_date.strftime("%Y%m%d"),
            end_date.strftime("%Y%m%d"),
            ticker,
        )
        if raw.empty:
            raise DataProviderError(
                "pykrx가 빈 데이터프레임을 반환했습니다. 티커가 잘못되었거나 해당 기간 데이터가 없습니다.",
                ticker=ticker,
                market="KR",
                selected_provider=self.__class__.__name__,
                source="pykrx",
                error_type="empty_dataframe",
                providers_tried=[{"name": "pykrx", "status": "error", "error": "empty dataframe"}],
            )

        frame = raw.reset_index().rename(
            columns={
                "날짜": "date",
                "시가": "open",
                "고가": "high",
                "저가": "low",
                "종가": "close",
                "거래량": "volume",
            }
        )
        return self._validate_frame(frame, ticker=ticker, market="KR", source="pykrx")

    def _fetch_finance_datareader(self, ticker: str, start_date: date, end_date: date) -> pd.DataFrame:
        import FinanceDataReader as fdr

        raw = fdr.DataReader(ticker, start_date.isoformat(), end_date.isoformat())
        if raw.empty:
            raise DataProviderError(
                "FinanceDataReader가 빈 데이터프레임을 반환했습니다.",
                ticker=ticker,
                market="KR",
                selected_provider=self.__class__.__name__,
                source="FinanceDataReader",
                error_type="empty_dataframe",
                providers_tried=[{"name": "FinanceDataReader", "status": "error", "error": "empty dataframe"}],
            )

        frame = raw.reset_index().rename(
            columns={
                "Date": "date",
                "Open": "open",
                "High": "high",
                "Low": "low",
                "Close": "close",
                "Volume": "volume",
            }
        )
        return self._validate_frame(frame, ticker=ticker, market="KR", source="FinanceDataReader")


class SampleDataProvider(BaseMarketDataProvider):
    name = "sample"

    def __init__(self) -> None:
        self.settings = get_settings()

    def fetch_ohlcv(self, ticker: str, period: str, market: Market = "US") -> PriceDataResult:  # type: ignore[override]
        df = self._generate_sample_history(ticker, PERIOD_TO_DAYS.get(period, 365) + 180)
        providers_tried = [self._success_try("sample", df)]
        return PriceDataResult(
            ticker=ticker,
            market=market,
            source="sample",
            is_sample=True,
            provider_status="fallback",
            provider_message="실데이터 조회 실패로 개발용 샘플 데이터를 사용했습니다.",
            data=df,
            selected_provider=self.__class__.__name__,
            providers_tried=providers_tried,
        )

    def _generate_sample_history(self, ticker: str, days: int) -> pd.DataFrame:
        seed_payload = f"{ticker}:{self.settings.SAMPLE_DATA_SEED}".encode("utf-8")
        seed = int.from_bytes(hashlib.sha256(seed_payload).digest()[:8], "big") % (2**32)
        rng = np.random.default_rng(seed)
        end = pd.Timestamp.utcnow().normalize()
        dates = pd.bdate_range(end=end, periods=max(days, 260))

        base_price = 45 + (seed % 350)
        drift = rng.normal(0.00035, 0.0002)
        volatility = 0.018 + (seed % 12) / 1000
        seasonal = np.sin(np.linspace(0, math.pi * 8, len(dates))) * 0.006
        shocks = rng.normal(drift, volatility, len(dates)) + seasonal
        close = base_price * np.exp(np.cumsum(shocks))
        open_ = close * (1 + rng.normal(0, 0.006, len(dates)))
        high = np.maximum(open_, close) * (1 + rng.uniform(0.002, 0.022, len(dates)))
        low = np.minimum(open_, close) * (1 - rng.uniform(0.002, 0.022, len(dates)))
        volume_base = 700_000 + (seed % 2_000_000)
        volume = np.maximum(10_000, volume_base * (1 + rng.normal(0, 0.22, len(dates)))).astype(int)

        return pd.DataFrame(
            {
                "date": dates.date,
                "open": np.round(open_, 2),
                "high": np.round(high, 2),
                "low": np.round(low, 2),
                "close": np.round(close, 2),
                "volume": volume,
            }
        )


class StockDataProvider:
    """Selects the right real data provider, then optionally uses sample fallback."""

    def __init__(self) -> None:
        self.settings = get_settings()
        self.yahoo_provider = YahooDataProvider()
        self.kr_provider = KoreanStockDataProvider()
        self.sample_provider = SampleDataProvider()
        self._cache: dict[tuple[str, str, str, str, bool], tuple[datetime, PriceDataResult]] = {}
        self._cache_lock = Lock()

    def fetch_ohlcv(self, ticker: str, period: str = "1y", *, force_refresh: bool = False) -> PriceDataResult:
        normalized_ticker = self.normalize_ticker(ticker)
        market = self.detect_market(normalized_ticker)
        provider = self._select_provider(market)
        cache_key = (
            normalized_ticker,
            market,
            period,
            self.settings.DATA_PROVIDER.strip().lower(),
            self.settings.ALLOW_SAMPLE_FALLBACK,
        )

        if not force_refresh:
            cached = self._get_cached_result(cache_key)
            if cached is not None:
                return cached

        last_error: DataProviderError | None = None
        for attempt in range(2):
            try:
                result = provider.fetch_ohlcv(normalized_ticker, period)
                self._set_cached_result(cache_key, result)
                return self._clone_result(result)
            except DataProviderError as exc:
                last_error = exc
                if attempt == 0 and exc.error_type == "network_or_api_error":
                    continue
                break

        if last_error is None:
            last_error = DataProviderError(
                "데이터 제공자 호출에 실패했습니다.",
                ticker=normalized_ticker,
                market=market,
                selected_provider=provider.__class__.__name__,
                source="none",
                error_type="provider_error",
                providers_tried=[],
            )

        exc = last_error
        self._log_provider_error(exc)
        if self.settings.ALLOW_SAMPLE_FALLBACK:
            sample = self.sample_provider.fetch_ohlcv(normalized_ticker, period, market)
            sample.provider_error = exc.message
            sample.provider_message = (
                f"{provider.name} 데이터 조회 실패로 개발용 샘플 데이터를 사용했습니다."
            )
            sample.selected_provider = provider.__class__.__name__
            sample.providers_tried = exc.providers_tried + sample.providers_tried
            self._set_cached_result(cache_key, sample)
            return self._clone_result(sample)
        raise DataProviderError(
            exc.message,
            ticker=normalized_ticker,
            market=market,
            selected_provider=provider.__class__.__name__,
            source="none",
            error_type=exc.error_type,
            providers_tried=exc.providers_tried,
        ) from exc

    def _get_cached_result(self, cache_key: tuple[str, str, str, str, bool]) -> PriceDataResult | None:
        with self._cache_lock:
            cached = self._cache.get(cache_key)
        if not cached:
            return None
        cached_at, result = cached
        if datetime.utcnow() - cached_at >= timedelta(seconds=self.settings.DATA_CACHE_TTL_SECONDS):
            with self._cache_lock:
                self._cache.pop(cache_key, None)
            return None
        return self._clone_result(result)

    def _set_cached_result(self, cache_key: tuple[str, str, str, str, bool], result: PriceDataResult) -> None:
        with self._cache_lock:
            self._cache[cache_key] = (datetime.utcnow(), self._clone_result(result))

    def _clone_result(self, result: PriceDataResult) -> PriceDataResult:
        return PriceDataResult(
            ticker=result.ticker,
            market=result.market,
            source=result.source,
            is_sample=result.is_sample,
            provider_status=result.provider_status,
            provider_message=result.provider_message,
            provider_error=result.provider_error,
            data=result.data.copy(),
            selected_provider=result.selected_provider,
            providers_tried=[dict(item) for item in result.providers_tried],
        )

    def _fetch_ohlcv_uncached_legacy(self, ticker: str, period: str = "1y") -> PriceDataResult:
        normalized_ticker = self.normalize_ticker(ticker)
        market = self.detect_market(normalized_ticker)
        provider = self._select_provider(market)

        try:
            return provider.fetch_ohlcv(normalized_ticker, period)
        except DataProviderError as exc:
            self._log_provider_error(exc)
            if self.settings.ALLOW_SAMPLE_FALLBACK:
                sample = self.sample_provider.fetch_ohlcv(normalized_ticker, period, market)
                sample.provider_error = exc.message
                sample.provider_message = (
                    f"{provider.name} 데이터 조회 실패로 개발용 샘플 데이터를 사용했습니다."
                )
                sample.selected_provider = provider.__class__.__name__
                sample.providers_tried = exc.providers_tried + sample.providers_tried
                return sample
            raise DataProviderError(
                exc.message,
                ticker=normalized_ticker,
                market=market,
                selected_provider=provider.__class__.__name__,
                source="none",
                error_type=exc.error_type,
                providers_tried=exc.providers_tried,
            ) from exc

    def debug_fetch(self, ticker: str, period: str = "1y") -> dict[str, Any]:
        normalized_ticker = self.normalize_ticker(ticker)
        try:
            market = self.detect_market(normalized_ticker)
            provider = self._select_provider(market)
            result = self.fetch_ohlcv(ticker, period)
            payload = result.debug_payload(ticker)
            payload["selected_provider"] = provider.__class__.__name__
            return payload
        except DataProviderError as exc:
            self._log_provider_error(exc)
            return exc.to_payload(ticker)

    def get_history(self, ticker: str, period: str = "1y") -> tuple[pd.DataFrame, str]:
        result = self.fetch_ohlcv(ticker, period)
        return result.data, result.source

    def get_quote(self, ticker: str, period: str = "1y") -> dict[str, Any]:
        result = self.fetch_ohlcv(ticker, period)
        latest = result.data.iloc[-1]
        previous = result.data.iloc[-2] if len(result.data) > 1 else latest
        previous_close = float(previous["close"]) if float(previous["close"]) else float(latest["close"])
        change = float(latest["close"] - previous["close"])

        return {
            "ticker": result.ticker,
            "period": period,
            "current_price": round(float(latest["close"]), 2),
            "previous_close": round(previous_close, 2),
            "change": round(change, 2),
            "change_rate": round(change / previous_close * 100 if previous_close else 0.0, 2),
            "volume": int(latest["volume"]),
            "last_updated": datetime.utcnow(),
            **result.metadata(),
        }

    def resolve_ticker(self, ticker: str) -> str:
        return self.normalize_ticker(ticker)

    def normalize_ticker(self, ticker: str) -> str:
        compact = ticker.strip().replace(" ", "")
        alias = TICKER_ALIASES.get(compact, TICKER_ALIASES.get(compact.upper(), compact))
        cleaned = alias.strip().upper()
        # 보안: URL/경로 주입 방어. 정상 티커엔 등장하지 않는 메타문자·제어문자 차단.
        # (한글 종목명은 통과시켜 detect_market에서 형식 안내 메시지로 처리)
        if any(ch in cleaned for ch in "/\\%?#&") or any(ord(ch) < 32 for ch in cleaned):
            raise DataProviderError(
                "허용되지 않는 문자가 포함된 티커입니다.",
                ticker=ticker,
                market="UNKNOWN",
                selected_provider=None,
                source="none",
                error_type="invalid_ticker_format",
                providers_tried=[],
            )
        if cleaned.endswith(".KS") or cleaned.endswith(".KQ"):
            return cleaned[:-3]
        return cleaned

    def detect_market(self, ticker: str) -> Market:
        if re.fullmatch(r"\d{6}", ticker):
            return "KR"
        if ticker.endswith(".KS") or ticker.endswith(".KQ"):
            return "KR"
        if re.fullmatch(r"[A-Z.]{1,10}", ticker):
            return "US"
        raise DataProviderError(
            "티커 형식을 판별할 수 없습니다. 한국 주식은 6자리 숫자, 해외 주식은 영문 티커를 입력하세요.",
            ticker=ticker,
            market="UNKNOWN",
            selected_provider=None,
            source="none",
            error_type="invalid_ticker_format",
            providers_tried=[],
        )

    def _select_provider(self, market: Market) -> BaseMarketDataProvider:
        provider = self.settings.DATA_PROVIDER.strip().lower()
        if provider == "auto":
            return self.kr_provider if market == "KR" else self.yahoo_provider
        if provider in {"kr", "korea", "pykrx", "finance-datareader", "financedatareader"}:
            return self.kr_provider
        if provider in {"us", "yahoo", "yfinance"}:
            return self.yahoo_provider
        return self.kr_provider if market == "KR" else self.yahoo_provider

    def _log_provider_error(self, error: DataProviderError) -> None:
        if self.settings.LOG_DATA_PROVIDER_ERRORS:
            logger.warning(
                "Data provider failed: ticker=%s market=%s provider=%s error_type=%s error=%s tried=%s",
                error.ticker,
                error.market,
                error.selected_provider,
                error.error_type,
                error.message,
                error.providers_tried,
            )
