"""IC verdict 임계값 단위 테스트."""
from app.services.ic_service import _verdict


def test_verdict_strong():
    assert _verdict(0.06, 0.4) == "강함"


def test_verdict_moderate():
    assert _verdict(0.04, 0.1) == "보통"


def test_verdict_weak():
    assert _verdict(0.02, 0.05) == "약함"


def test_verdict_meaningless():
    assert _verdict(0.005, 0.01) == "무의미"


def test_verdict_negative_ic_abs():
    # 음의 IC도 절댓값으로 판정 (저변동 팩터 등)
    assert _verdict(-0.06, -0.4) == "강함"
