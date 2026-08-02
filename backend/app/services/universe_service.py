from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import logging
from threading import Lock
from typing import Any, Literal

import pandas as pd

from app.core.config import get_settings
from app.core.stock_universe import KOREAN_REPRESENTATIVE_STOCKS, US_REPRESENTATIVE_STOCKS, StockUniverseItem


MarketFilter = Literal["all", "KR", "US"]
UniverseSource = Literal["auto", "fallback"]

logger = logging.getLogger("app.services.universe")


@dataclass(frozen=True)
class UniverseResult:
    market: MarketFilter
    source: str
    items: list[StockUniverseItem]
    kr_count: int
    us_count: int
    updated_at: datetime


class UniverseService:
    """Builds representative KR/US stock universes with dynamic lookup and fallback lists."""

    def __init__(self) -> None:
        self.settings = get_settings()
        self._cache: dict[tuple[str, int, int, str], tuple[datetime, UniverseResult]] = {}
        self._lock = Lock()

    def get_representative_stocks(
        self,
        market: MarketFilter = "all",
        kr_limit: int = 100,
        us_limit: int = 100,
        source: UniverseSource = "auto",
        *,
        force_refresh: bool = False,
    ) -> UniverseResult:
        normalized_market = market if market in {"all", "KR", "US"} else "all"
        normalized_source = source if source in {"auto", "fallback"} else "auto"
        kr_limit = max(0, min(int(kr_limit), 100))
        us_limit = max(0, min(int(us_limit), 100))
        cache_key = (normalized_market, kr_limit, us_limit, normalized_source)
        now = datetime.utcnow()

        if not force_refresh:
            with self._lock:
                cached = self._cache.get(cache_key)
            if cached and now - cached[0] < timedelta(seconds=self.settings.UNIVERSE_CACHE_TTL_SECONDS):
                return cached[1]

        kr_items: list[StockUniverseItem] = []
        us_items: list[StockUniverseItem] = []
        source_parts: list[str] = []

        if normalized_market in {"all", "KR"} and kr_limit:
            kr_items, kr_source = self._get_kr_universe(kr_limit, normalized_source)
            source_parts.append(kr_source)

        if normalized_market in {"all", "US"} and us_limit:
            us_items, us_source = self._get_us_universe(us_limit, normalized_source)
            source_parts.append(us_source)

        items = kr_items + us_items
        source_label = self._source_label(source_parts, normalized_source)
        result = UniverseResult(
            market=normalized_market,
            source=source_label,
            items=items,
            kr_count=len(kr_items),
            us_count=len(us_items),
            updated_at=datetime.now(timezone(timedelta(hours=9))),
        )
        with self._lock:
            self._cache[cache_key] = (now, result)
        return result

    def _get_kr_universe(self, limit: int, source: UniverseSource) -> tuple[list[StockUniverseItem], str]:
        if source == "fallback":
            return self._fallback_kr(limit), "fallback"
        try:
            items = self._fetch_kr_by_market_cap(limit)
            if items:
                return items, "pykrx"
            raise RuntimeError("pykrx 시가총액 목록이 비어 있습니다.")
        except Exception as exc:
            logger.warning("KR universe lookup failed, using fallback: %s", exc)
            return self._fallback_kr(limit), "fallback"

    def _get_us_universe(self, limit: int, source: UniverseSource) -> tuple[list[StockUniverseItem], str]:
        if source == "fallback":
            return self._fallback_us(limit), "fallback"
        try:
            items = self._fetch_us_major_index_members(limit)
            if items:
                return items, "wikipedia"
            raise RuntimeError("미국 대표 지수 구성 종목 목록이 비어 있습니다.")
        except Exception as exc:
            logger.warning("US universe lookup failed, using fallback: %s", exc)
            return self._fallback_us(limit), "fallback"

    def _fetch_kr_by_market_cap(self, limit: int) -> list[StockUniverseItem]:
        from pykrx import stock

        today = datetime.utcnow().date()
        frames: list[pd.DataFrame] = []
        for offset in range(0, 14):
            target = today - timedelta(days=offset)
            target_text = target.strftime("%Y%m%d")
            try:
                frame = stock.get_market_cap_by_ticker(target_text, market="ALL")
            except TypeError:
                frame = stock.get_market_cap_by_ticker(target_text)
            if not frame.empty:
                frames.append(frame)
                break

        if not frames:
            return []

        frame = frames[0].copy()
        sort_columns = [column for column in ["시가총액", "거래대금", "거래량"] if column in frame.columns]
        if sort_columns:
            frame = frame.sort_values(sort_columns, ascending=[False] * len(sort_columns))

        items: list[StockUniverseItem] = []
        for ticker in frame.index.astype(str):
            normalized_ticker = ticker.zfill(6)
            name = stock.get_market_ticker_name(normalized_ticker) or normalized_ticker
            items.append({"name": name, "ticker": normalized_ticker, "market": "KR"})
            if len(items) >= limit:
                break
        return self._dedupe(items, limit)

    def _fetch_us_major_index_members(self, limit: int) -> list[StockUniverseItem]:
        items: list[StockUniverseItem] = []
        items.extend(self._read_wikipedia_table("https://en.wikipedia.org/wiki/Nasdaq-100", market="US"))
        if len(items) < limit:
            items.extend(self._read_wikipedia_table("https://en.wikipedia.org/wiki/List_of_S%26P_500_companies", market="US"))
        return self._dedupe(items, limit)

    def _read_wikipedia_table(self, url: str, market: Literal["US"]) -> list[StockUniverseItem]:
        tables = pd.read_html(url)
        candidates: list[StockUniverseItem] = []
        for table in tables:
            columns = {self._flatten_column(column): column for column in table.columns}
            ticker_column = self._find_column(columns, {"ticker", "symbol"})
            name_column = self._find_column(columns, {"company", "company name", "security"})
            if ticker_column is None or name_column is None:
                continue

            for _, row in table.iterrows():
                ticker = str(row[ticker_column]).strip().upper().replace(".", "-")
                name = str(row[name_column]).strip()
                if ticker and ticker.lower() != "nan" and name and name.lower() != "nan":
                    candidates.append({"name": name, "ticker": ticker, "market": market})
        return candidates

    def _fallback_kr(self, limit: int) -> list[StockUniverseItem]:
        return self._dedupe(KOREAN_REPRESENTATIVE_STOCKS, limit)

    def _fallback_us(self, limit: int) -> list[StockUniverseItem]:
        return self._dedupe(US_REPRESENTATIVE_STOCKS, limit)

    def _dedupe(self, items: list[StockUniverseItem], limit: int) -> list[StockUniverseItem]:
        seen: set[tuple[str, str]] = set()
        deduped: list[StockUniverseItem] = []
        for item in items:
            ticker = str(item["ticker"]).strip().upper()
            market = str(item["market"]).strip().upper()
            if market not in {"KR", "US"} or not ticker:
                continue
            key = (market, ticker)
            if key in seen:
                continue
            seen.add(key)
            deduped.append({"name": str(item["name"]).strip() or ticker, "ticker": ticker, "market": market})
            if len(deduped) >= limit:
                break
        return deduped

    def _flatten_column(self, column: Any) -> str:
        if isinstance(column, tuple):
            return " ".join(str(part).strip().lower() for part in column if str(part).strip())
        return str(column).strip().lower()

    def _find_column(self, columns: dict[str, Any], names: set[str]) -> Any | None:
        for normalized, original in columns.items():
            if normalized in names:
                return original
        for normalized, original in columns.items():
            if any(name in normalized for name in names):
                return original
        return None

    def _source_label(self, parts: list[str], requested_source: str) -> str:
        if requested_source == "fallback":
            return "fallback"
        unique = set(parts)
        if not unique:
            return requested_source
        if unique == {"fallback"}:
            return "fallback"
        if "fallback" in unique:
            return "mixed"
        return "auto"
