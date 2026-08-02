"""
뉴스 감성 서비스 — 가벼운 우회 (KoBERT 대신 금융 키워드 사전).

- 네이버 모바일 금융 뉴스 API (m.stock.naver.com) 제목 수집
- 한국어 금융 감성 사전으로 제목별 +/- 점수
- transformers/모델 다운로드 불필요. 즉시 작동.

한계: 사전 기반 → 문맥/반어 못 잡음. 제목만 분석. 차별화보다 신호 보조용.
캐시: 1시간.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from datetime import datetime
from threading import Lock

import requests

logger = logging.getLogger("news_sentiment")

_cache: dict[str, tuple[datetime, "NewsSentiment"]] = {}
_cache_lock = Lock()
_TTL = 3600
_HEADERS = {"User-Agent": "Mozilla/5.0"}

# 금융 감성 사전 (가중치)
_POSITIVE = {
    "급등": 3, "신고가": 3, "최대실적": 3, "흑자전환": 3, "어닝서프라이즈": 3,
    "수주": 2, "계약": 2, "호실적": 2, "실적개선": 2, "상향": 2, "매수": 2,
    "강세": 2, "반등": 2, "돌파": 2, "수혜": 2, "기대": 1, "성장": 2,
    "증가": 1, "개선": 1, "확대": 1, "호조": 2, "훈풍": 2, "회복": 2,
    "목표가상향": 3, "투자": 1, "공급": 1, "협력": 1, "신제품": 1, "흑자": 2,
    "사상최대": 3, "역대최대": 3, "흥행": 2, "낙관": 2, "순항": 2,
}
_NEGATIVE = {
    "급락": 3, "신저가": 3, "적자": 3, "적자전환": 3, "어닝쇼크": 3,
    "하향": 2, "매도": 2, "약세": 2, "폭락": 3, "하락": 2, "부진": 2,
    "감소": 1, "축소": 1, "악화": 2, "우려": 2, "리스크": 2, "위기": 2,
    "손실": 2, "감산": 2, "철수": 2, "소송": 2, "제재": 2, "조사": 1,
    "목표가하향": 3, "경고": 2, "추락": 3, "충격": 2, "타격": 2, "공포": 2,
    "디폴트": 3, "파산": 3, "횡령": 3, "배임": 3, "상장폐지": 3, "거래정지": 3,
}


# 중립/모호어 — 점수 전 선소거 (부분문자열 오탐 방지)
_NEUTRAL = ["급등락", "등락", "상장폐지 면제", "적자폭 축소"]

# 긍/부정 통합 후 길이 내림차순 정렬 (긴 단어 우선 매칭)
_SCORED_SORTED = sorted(
    [(w, p) for w, p in _POSITIVE.items()] + [(w, -p) for w, p in _NEGATIVE.items()],
    key=lambda x: len(x[0]),
    reverse=True,
)


def _is_kr(ticker: str) -> bool:
    return bool(re.fullmatch(r"\d{6}", ticker.strip()))


@dataclass
class NewsItem:
    title: str
    score: int          # 제목 감성 (+/-)


@dataclass
class NewsSentiment:
    ticker: str
    sentiment_score: float    # 0~100 (50 중립)
    label: str                # "긍정" / "중립" / "부정"
    positive_count: int
    negative_count: int
    total: int
    headlines: list[dict]     # 상위 제목 + 점수

    def to_dict(self) -> dict:
        return {
            "ticker": self.ticker,
            "sentiment_score": round(self.sentiment_score, 1),
            "label": self.label,
            "positive_count": self.positive_count,
            "negative_count": self.negative_count,
            "total": self.total,
            "headlines": self.headlines,
        }


class NewsSentimentService:
    def get(self, ticker: str) -> NewsSentiment | None:
        ticker = ticker.strip()
        if not _is_kr(ticker):
            return None  # 국내 종목만 (해외는 영어 사전 필요)
        with _cache_lock:
            cached = _cache.get(ticker)
        if cached and (datetime.utcnow() - cached[0]).total_seconds() < _TTL:
            return cached[1]
        try:
            ns = self._fetch(ticker)
        except Exception as exc:
            logger.warning(f"뉴스 감성 실패 {ticker}: {exc}")
            return None
        if ns:
            with _cache_lock:
                _cache[ticker] = (datetime.utcnow(), ns)
        return ns

    def _fetch(self, ticker: str) -> NewsSentiment | None:
        url = f"https://m.stock.naver.com/api/news/stock/{ticker}?pageSize=30&page=1"
        resp = requests.get(url, headers=_HEADERS, timeout=10)
        titles = re.findall(r'"title"\s*:\s*"([^"]{6,})"', resp.text)
        # 중복 제거 + HTML 엔티티 정리
        seen, clean = set(), []
        for t in titles:
            t = t.replace("&quot;", '"').replace("&amp;", "&").replace("\\", "").strip()
            if t and t not in seen:
                seen.add(t)
                clean.append(t)
        if not clean:
            return None

        items: list[NewsItem] = []
        pos = neg = 0
        for title in clean[:25]:
            score = self._score_title(title)
            items.append(NewsItem(title=title, score=score))
            if score > 0: pos += 1
            elif score < 0: neg += 1

        total = len(items)
        # 감성 점수: 50 + (긍정-부정 가중합 정규화)
        net = sum(i.score for i in items)
        raw = 50 + net * 2.5
        sentiment_score = max(0.0, min(100.0, raw))
        label = "긍정" if sentiment_score >= 60 else "부정" if sentiment_score <= 40 else "중립"

        # 점수 절댓값 큰 제목 우선 노출
        top = sorted(items, key=lambda i: abs(i.score), reverse=True)[:6]
        headlines = [{"title": i.title, "score": i.score} for i in top]

        return NewsSentiment(
            ticker=ticker,
            sentiment_score=sentiment_score,
            label=label,
            positive_count=pos,
            negative_count=neg,
            total=total,
            headlines=headlines,
        )

    def _score_title(self, title: str) -> int:
        """긴 단어 우선 + 매칭 구간 소거로 부분문자열 오탐 방지.
        예: '급등락'(중립) 먼저 소거 → 그 안의 '급등'(+) 재매칭 차단."""
        work = title
        # 중립 모호어 선소거 (급등락, 등락 등 → 변별 안 함)
        for neutral in _NEUTRAL:
            work = work.replace(neutral, " ")

        score = 0
        # 긴 키워드부터 매칭 후 해당 구간 공백 치환 → 내부 짧은 단어 재매칭 방지
        for word, w in _SCORED_SORTED:
            if word in work:
                score += w
                work = work.replace(word, " ")
        return max(-3, min(3, score))  # 제목당 ±3 제한
