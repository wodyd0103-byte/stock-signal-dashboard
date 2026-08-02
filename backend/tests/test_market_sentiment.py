"""공포·탐욕 점수 매핑 단위 테스트 (네트워크 없음)."""
from app.services.market_sentiment_service import _label, _linear_score


def test_linear_score_basic():
    assert _linear_score(10, 0, 100) == 10
    assert _linear_score(50, 0, 100) == 50


def test_linear_score_invert():
    # 공포지표: 낮을수록 높은 점수
    assert _linear_score(0, 0, 100, invert=True) == 100
    assert _linear_score(100, 0, 100, invert=True) == 0


def test_linear_score_clamp():
    assert _linear_score(200, 0, 100) == 100
    assert _linear_score(-50, 0, 100) == 0


def test_labels():
    assert _label(10) == "극도 공포"
    assert _label(35) == "공포"
    assert _label(50) == "중립"
    assert _label(65) == "탐욕"
    assert _label(90) == "극도 탐욕"
