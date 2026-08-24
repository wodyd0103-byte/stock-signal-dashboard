"""digest 스냅샷 저장과 전일 대비 비교.

리포트를 매일 파일로 남기고, 직전 스냅샷과 신호를 비교해 "어제 HOLD였는데 오늘 BUY"
같은 변화를 뽑는다. 이 변화 목록이 digest의 실질 가치라서 렌더러보다 먼저 계산한다.

출력 디렉터리에는 보유 종목과 평단가가 들어간다. 개인 정보라 `.gitignore`에 넣었다.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import date, datetime
from pathlib import Path

from tools.digest.collector import Digest

DEFAULT_DIR = Path(__file__).resolve().parents[2] / "data" / "digest"

# 강도 순. 인덱스 차이로 상승/하락 전환을 판단한다.
SIGNAL_ORDER = ["STRONG SELL", "SELL", "WEAK SELL", "HOLD", "WEAK BUY", "BUY", "STRONG BUY"]


@dataclass
class Change:
    """직전 스냅샷 대비 신호 변화 한 건."""

    ticker: str
    name: str | None
    previous: str | None  # None이면 이번에 새로 들어온 종목
    current: str
    direction: str  # "up" | "down" | "new"

    @property
    def is_new(self) -> bool:
        return self.previous is None


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


def diff_signals(digest: Digest, previous: dict | None) -> list[Change]:
    """신호가 바뀐 종목만 추린다. 변화 없는 종목은 나오지 않는다."""
    if previous is None:
        return []

    before = {row["ticker"]: row.get("signal") for row in previous.get("rows", [])}
    changes: list[Change] = []

    for row in digest.rows:
        old = before.get(row.ticker)
        if old == row.signal:
            continue
        if old is None:
            changes.append(Change(row.ticker, row.name, None, row.signal, "new"))
            continue

        try:
            direction = "up" if SIGNAL_ORDER.index(row.signal) > SIGNAL_ORDER.index(old) else "down"
        except ValueError:
            # 스키마가 바뀌어 모르는 신호가 들어오면 방향 판단을 포기하고 변화만 남긴다.
            direction = "up"
        changes.append(Change(row.ticker, row.name, old, row.signal, direction))

    # 상승 전환을 위로. 같은 방향이면 티커 순.
    rank = {"up": 0, "new": 1, "down": 2}
    changes.sort(key=lambda c: (rank.get(c.direction, 3), c.ticker))
    return changes


def previous_generated_at(previous: dict | None) -> datetime | None:
    if not previous:
        return None
    try:
        return datetime.fromisoformat(previous["generated_at"])
    except (KeyError, ValueError):
        return None
