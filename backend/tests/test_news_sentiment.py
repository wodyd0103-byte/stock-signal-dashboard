"""뉴스 감성 키워드 채점 — 부분문자열 오탐 방지 포함."""
from app.services.news_sentiment_service import NewsSentimentService


def test_positive_keyword():
    s = NewsSentimentService()
    assert s._score_title("삼성전자 사상최대 실적 호조") > 0


def test_negative_keyword():
    s = NewsSentimentService()
    assert s._score_title("적자전환 충격에 급락") < 0


def test_substring_guard_geupdeungrak():
    # '급등락'(중립)이 '급등'(+)으로 오탐되면 안 됨
    s = NewsSentimentService()
    score = s._score_title("증시 급등락 반복")
    assert score <= 0  # 급등 가산 차단


def test_score_clamped():
    s = NewsSentimentService()
    # 긍정어 다수라도 ±3 제한
    score = s._score_title("급등 신고가 최대실적 흑자전환 수주 호실적")
    assert -3 <= score <= 3


def test_only_kr_ticker():
    s = NewsSentimentService()
    assert s.get("AAPL") is None  # 해외는 None
