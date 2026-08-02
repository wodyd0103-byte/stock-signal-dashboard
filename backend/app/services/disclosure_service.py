"""
공시 서비스 — 최근 공시 수집 + 키워드 분류 (네이버, DART 키 불요).

OpenDART는 API 키 필요 → 가벼운 우회로 네이버 모바일 공시 API 사용.
공시 제목을 카테고리(실적/자금조달/계약/배당/자사주/구조)로 태깅.
'중요 공시'(유상증자, 실적, 대형계약 등) 플래그.
캐시: 1시간. 국내 종목만.
"""
from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass
from threading import Lock

import requests

logger = logging.getLogger("disclosure")

_cache: dict[str, tuple[float, "DisclosureInfo"]] = {}
_cache_lock = Lock()
_TTL = 3600
_HEADERS = {"User-Agent": "Mozilla/5.0"}

# (카테고리, 키워드, 중요도, 성향)  성향: +호재 -악재 0중립
_RULES = [
    ("실적", ["잠정실적", "영업(잠정)", "매출액또는손익", "결산실적"], True, 0),
    ("자금조달", ["유상증자", "전환사채", "신주인수권", "교환사채"], True, -1),
    ("자사주", ["자기주식취득", "자사주", "자기주식소각"], True, 1),
    ("계약", ["단일판매", "공급계약", "수주", "계약체결"], True, 1),
    ("배당", ["현금ㆍ현물배당", "배당", "주주환원"], False, 1),
    ("구조", ["합병", "분할", "영업양수도", "주식교환"], True, 0),
    ("지분", ["최대주주", "주식등의대량보유", "임원ㆍ주요주주"], False, 0),
]


def _is_kr(t: str) -> bool:
    return bool(re.fullmatch(r"\d{6}", t.strip()))


@dataclass
class DisclosureItem:
    title: str
    datetime: str
    author: str
    category: str
    important: bool
    sentiment: int  # +1 / 0 / -1


@dataclass
class DisclosureInfo:
    ticker: str
    items: list[DisclosureItem]
    important_count: int
    has_dilution: bool   # 유상증자 등 희석 이벤트

    def to_dict(self) -> dict:
        return {
            "ticker": self.ticker,
            "important_count": self.important_count,
            "has_dilution": self.has_dilution,
            "items": [
                {
                    "title": i.title, "datetime": i.datetime, "author": i.author,
                    "category": i.category, "important": i.important, "sentiment": i.sentiment,
                }
                for i in self.items
            ],
        }


class DisclosureService:
    def get(self, ticker: str) -> DisclosureInfo | None:
        ticker = ticker.strip()
        if not _is_kr(ticker):
            return None
        with _cache_lock:
            hit = _cache.get(ticker)
        if hit and (time.time() - hit[0]) < _TTL:
            return hit[1]
        try:
            info = self._fetch(ticker)
        except Exception as exc:
            logger.warning(f"공시 수집 실패 {ticker}: {exc}")
            return None
        if info:
            with _cache_lock:
                _cache[ticker] = (time.time(), info)
        return info

    def _fetch(self, ticker: str) -> DisclosureInfo | None:
        url = f"https://m.stock.naver.com/api/stock/{ticker}/disclosure?pageSize=15&page=1"
        data = requests.get(url, headers=_HEADERS, timeout=8).json()
        if not isinstance(data, list) or not data:
            return DisclosureInfo(ticker, [], 0, False)

        items: list[DisclosureItem] = []
        for row in data[:15]:
            title = str(row.get("title", "")).strip()
            if not title:
                continue
            cat, important, sentiment = self._classify(title)
            items.append(DisclosureItem(
                title=title,
                datetime=str(row.get("datetime", "")),
                author=str(row.get("author", "")),
                category=cat, important=important, sentiment=sentiment,
            ))

        important_count = sum(1 for i in items if i.important)
        has_dilution = any(i.category == "자금조달" and i.sentiment < 0 for i in items)
        return DisclosureInfo(ticker, items, important_count, has_dilution)

    def _classify(self, title: str) -> tuple[str, bool, int]:
        for cat, keywords, important, sentiment in _RULES:
            if any(k in title for k in keywords):
                return cat, important, sentiment
        return "기타", False, 0
