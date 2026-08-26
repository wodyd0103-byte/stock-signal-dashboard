"""digest 스냅샷 저장과 전일 대비 비교.

리포트를 매일 파일로 남기고, 직전 스냅샷과 신호를 비교해 "어제 HOLD였는데 오늘 BUY"
같은 변화를 뽑는다. 이 변화 목록이 digest의 실질 가치라서 렌더러보다 먼저 계산한다.

출력 디렉터리에는 보유 종목과 평단가가 들어간다. 개인 정보라 `.gitignore`에 넣었다.
"""
from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from datetime import date, datetime
from pathlib import Path

from tools.digest.collector import Digest

DEFAULT_DIR = Path(__file__).resolve().parents[2] / "data" / "digest"

# 강도 순. 인덱스 차이로 상승/하락 전환을 판단한다.
SIGNAL_ORDER = ["STRONG SELL", "SELL", "WEAK SELL", "HOLD", "WEAK BUY", "BUY", "STRONG BUY"]

# 위험이 낮은 순. 리스크는 내려가는 쪽이 좋은 소식이다.
RISK_ORDER = ["낮음", "보통", "높음", "매우 높음"]


# 신호 등급이 안 바뀌어도 점수는 크게 움직인다. 등급만 보면 "어제와 같다"고 말하게 되는데
# 매수점수가 1에서 18로 뛴 날은 같은 날이 아니다. 등급 경계를 넘지 않은 이동도 보고한다.
SCORE_MOVE_FLOOR = max(1, int(os.getenv("DIGEST_SCORE_MOVE_FLOOR", "15")))

KIND_SIGNAL = "signal"
KIND_SCORE = "score"
KIND_RISK = "risk"


@dataclass
class Change:
    """직전 스냅샷 대비 변화 한 건.

    kind 가 무엇이 바뀌었는지 말한다.
    - signal: 신호 등급 (HOLD → BUY). 가장 강한 신호다.
    - score: 등급은 그대로지만 매수점수가 크게 움직였다.
    - risk: 리스크 등급이 바뀌었다 (높음 → 보통).
    """

    ticker: str
    name: str | None
    previous: str | None  # None이면 이번에 새로 들어온 종목
    current: str
    direction: str  # "up" | "down" | "new"
    kind: str = KIND_SIGNAL

    @property
    def is_new(self) -> bool:
        return self.previous is None

    @property
    def is_signal(self) -> bool:
        return self.kind == KIND_SIGNAL


def snapshot_path(directory: Path | None = None, on: date | None = None) -> Path:
    directory = directory or DEFAULT_DIR
    return directory / f"{(on or date.today()).isoformat()}.json"


def save_snapshot(digest: Digest, directory: Path | None = None) -> Path:
    """오늘 자 스냅샷을 쓴다. 같은 날 두 번 돌리면 덮어쓴다."""
    directory = directory or DEFAULT_DIR
    directory.mkdir(parents=True, exist_ok=True)
    path = snapshot_path(directory, digest.generated_at.date())

    payload = {
        "generated_at": digest.generated_at.isoformat(timespec="seconds"),
        "period": digest.period,
        "rows": [asdict(row) for row in digest.rows],
        "failures": [asdict(failure) for failure in digest.failures],
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def load_previous(directory: Path | None = None, before: date | None = None) -> dict | None:
    """`before`보다 앞선 스냅샷 중 가장 최근 것. 없으면 None.

    "어제" 파일을 고정으로 찾지 않는다. 주말이나 며칠 걸렀을 때도 마지막으로 돌린
    결과와 비교해야 변화가 의미를 가진다.
    """
    directory = directory or DEFAULT_DIR
    if not directory.exists():
        return None

    cutoff = (before or date.today()).isoformat()
    candidates = sorted(p for p in directory.glob("*.json") if p.stem < cutoff)
    if not candidates:
        return None

    try:
        return json.loads(candidates[-1].read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def diff_signals(digest: Digest, previous: dict | None, score_floor: int | None = None) -> list[Change]:
    """직전 스냅샷 이후 달라진 것만 추린다. 변화 없는 종목은 나오지 않는다.

    한 종목에서 신호 등급이 바뀌었으면 그 종목의 점수 이동은 따로 보고하지 않는다.
    등급이 바뀔 정도면 점수도 당연히 움직였고, 같은 사실을 두 줄로 말하면 소음이다.
    """
    if previous is None:
        return []

    floor = SCORE_MOVE_FLOOR if score_floor is None else max(1, score_floor)
    before = {row["ticker"]: row for row in previous.get("rows", [])}
    changes: list[Change] = []

    for row in digest.rows:
        old_row = before.get(row.ticker)

        if old_row is None:
            changes.append(Change(row.ticker, row.name, None, row.signal, "new", KIND_SIGNAL))
            continue

        old_signal = old_row.get("signal")
        if old_signal != row.signal:
            changes.append(
                Change(row.ticker, row.name, old_signal, row.signal, _signal_direction(old_signal, row.signal), KIND_SIGNAL)
            )
            continue

        # 등급은 그대로. 점수와 리스크가 얼마나 움직였는지 본다.
        old_score = old_row.get("final_buy_score")
        if isinstance(old_score, int) and abs(row.final_buy_score - old_score) >= floor:
            changes.append(
                Change(
                    row.ticker,
                    row.name,
                    str(old_score),
                    str(row.final_buy_score),
                    "up" if row.final_buy_score > old_score else "down",
                    KIND_SCORE,
                )
            )

        old_risk = old_row.get("risk_level")
        if old_risk and old_risk != row.risk_level:
            changes.append(
                Change(
                    row.ticker,
                    row.name,
                    old_risk,
                    row.risk_level,
                    _risk_direction(old_risk, row.risk_level),
                    KIND_RISK,
                )
            )

    # 등급 변화가 먼저. 그중에서도 상승 전환을 위로.
    kind_rank = {KIND_SIGNAL: 0, KIND_SCORE: 1, KIND_RISK: 2}
    direction_rank = {"up": 0, "new": 1, "down": 2}
    changes.sort(
        key=lambda c: (kind_rank.get(c.kind, 9), direction_rank.get(c.direction, 3), c.ticker)
    )
    return changes


def _signal_direction(previous: str | None, current: str) -> str:
    try:
        return "up" if SIGNAL_ORDER.index(current) > SIGNAL_ORDER.index(previous) else "down"
    except ValueError:
        # 스키마가 바뀌어 모르는 신호가 들어오면 방향 판단을 포기하고 변화만 남긴다.
        return "up"


def _risk_direction(previous: str, current: str) -> str:
    """리스크가 낮아지면 좋은 소식이라 up 으로 본다."""
    try:
        return "up" if RISK_ORDER.index(current) < RISK_ORDER.index(previous) else "down"
    except ValueError:
        return "down"


def previous_generated_at(previous: dict | None) -> datetime | None:
    if not previous:
        return None
    try:
        return datetime.fromisoformat(previous["generated_at"])
    except (KeyError, ValueError):
        return None
