"""digest 출력 — 터미널 표, 마크다운, 단독 HTML.

세 포맷이 같은 순서와 같은 컬럼을 쓴다. 아침에 터미널에서 본 것과 파일로 열어본 것이
달라 보이면 안 된다.
"""
from __future__ import annotations

import html
from datetime import datetime
from unicodedata import east_asian_width

from tools.digest.collector import Digest, Row
from tools.digest.store import Change

RESET = "\033[0m"
DIM = "\033[2m"
BOLD = "\033[1m"
GREEN = "\033[32m"
RED = "\033[31m"
YELLOW = "\033[33m"
GREY = "\033[90m"

_SIGNAL_COLOR = {
    "STRONG BUY": GREEN + BOLD,
    "BUY": GREEN,
    "WEAK BUY": GREEN + DIM,
    "HOLD": GREY,
    "WEAK SELL": RED + DIM,
    "SELL": RED,
    "STRONG SELL": RED + BOLD,
}

COLUMNS = ("종목", "현재가", "등락", "신호", "매수점수", "리스크", "손익")

# 이력 요약 창. history.recent()의 기본값과 맞춘다.
HISTORY_WINDOW_DAYS = 30


def _width(text: str) -> int:
    """한글·전각 문자는 터미널에서 두 칸을 먹는다."""
    return sum(2 if east_asian_width(ch) in "WF" else 1 for ch in text)


def _pad(text: str, width: int, align: str = "left") -> str:
    gap = max(0, width - _width(text))
    return (" " * gap + text) if align == "right" else (text + " " * gap)


def _label(row: Row) -> str:
    return f"{row.name} ({row.ticker})" if row.name else row.ticker


def _pnl_text(row: Row) -> str:
    return "-" if row.pnl_pct is None else f"{row.pnl_pct:+.1f}%"


def _cells(row: Row) -> tuple[str, ...]:
    return (
        _label(row),
        f"{row.current_price:,.0f}",
        f"{row.change_rate:+.2f}%",
        row.signal,
        str(row.final_buy_score),
        f"{row.risk_score} {row.risk_level}",
        _pnl_text(row),
    )


def _sentiment_line(digest: Digest) -> str | None:
    sentiment = digest.market_sentiment or {}
    score, label = sentiment.get("score"), sentiment.get("label")
    if score is None:
        return None
    return f"시장심리 {score}/100 ({label})" if label else f"시장심리 {score}/100"


def _header_lines(digest: Digest, previous_at: datetime | None) -> list[str]:
    stamp = digest.generated_at.strftime("%Y-%m-%d %H:%M")
    lines = [f"{stamp} · 기간 {digest.period} · 분석 {len(digest.rows)}건 / 실패 {len(digest.failures)}건"]
    sentiment = _sentiment_line(digest)
    if sentiment:
        lines.append(sentiment)
    if previous_at:
        lines.append(f"직전 비교 기준: {previous_at.strftime('%Y-%m-%d %H:%M')}")
    return lines


def _change_text(change: Change) -> str:
    if change.is_new:
        return f"신규 {change.current}"
    return f"{change.previous} → {change.current}"


# 한 번은 오늘의 전환일 뿐이라 셀 것이 없다. 두 번부터가 "오락가락한다"는 신호다.
_FLIP_NOTE_FLOOR = 2


def _flip_note(change: Change, flips: dict[str, int]) -> str:
    """이 종목이 최근에 몇 번 뒤집혔는지. 오늘의 변화를 얼마나 믿을지의 재료."""
    count = flips.get(change.ticker, 0)
    if count < _FLIP_NOTE_FLOOR:
        return ""
    return f"{HISTORY_WINDOW_DAYS}일 {count}회"


def render_terminal(
    digest: Digest,
    changes: list[Change] | None = None,
    previous_at: datetime | None = None,
    flips: dict[str, int] | None = None,
) -> str:
    changes = changes or []
    flips = flips or {}
    out: list[str] = []

    for line in _header_lines(digest, previous_at):
        out.append(f"{DIM}{line}{RESET}")
    out.append("")

    if changes:
        out.append(f"{BOLD}신호 변화{RESET}")
        for change in changes:
            colour = GREEN if change.direction == "up" else (YELLOW if change.is_new else RED)
            name = change.name or change.ticker
            note = _flip_note(change, flips)
            suffix = f"  {DIM}· {note}{RESET}" if note else ""
            out.append(f"  {colour}●{RESET} {name} ({change.ticker})  {_change_text(change)}{suffix}")
        out.append("")

    if not digest.rows:
        out.append(f"{DIM}분석된 종목이 없습니다. 관심종목이나 보유 종목을 먼저 등록하세요.{RESET}")
    else:
        cells = [_cells(row) for row in digest.rows]
        widths = [
            max(_width(COLUMNS[i]), max(_width(cell[i]) for cell in cells))
            for i in range(len(COLUMNS))
        ]
        aligns = ("left", "right", "right", "left", "right", "left", "right")

        head = "  ".join(_pad(COLUMNS[i], widths[i], aligns[i]) for i in range(len(COLUMNS)))
        out.append(f"{DIM}{head}{RESET}")
        out.append(f"{DIM}{'─' * _width(head)}{RESET}")

        for row, cell in zip(digest.rows, cells):
            colour = _SIGNAL_COLOR.get(row.signal, "")
            parts = [
                _pad(cell[0], widths[0]),
                _pad(cell[1], widths[1], "right"),
                (GREEN if row.change_rate > 0 else RED if row.change_rate < 0 else "")
                + _pad(cell[2], widths[2], "right") + RESET,
                colour + _pad(cell[3], widths[3]) + RESET,
                _pad(cell[4], widths[4], "right"),
                _pad(cell[5], widths[5]),
                _pad(cell[6], widths[6], "right"),
            ]
            out.append("  ".join(parts))

    if digest.failures:
        out.append("")
        out.append(f"{BOLD}실패{RESET}")
        for failure in digest.failures:
            out.append(f"  {RED}×{RESET} {failure.ticker}  {DIM}{failure.error}{RESET}")

    return "\n".join(out)


def render_markdown(
    digest: Digest,
    changes: list[Change] | None = None,
    previous_at: datetime | None = None,
    flips: dict[str, int] | None = None,
) -> str:
    changes = changes or []
    flips = flips or {}
    out = [f"# 관심종목 리포트 {digest.generated_at.strftime('%Y-%m-%d')}", ""]
    out += [f"- {line}" for line in _header_lines(digest, previous_at)]
    out.append("")

    if changes:
        out += ["## 신호 변화", ""]
        for change in changes:
            marker = {"up": "▲", "down": "▼", "new": "＋"}.get(change.direction, "·")
            name = change.name or change.ticker
            note = _flip_note(change, flips)
            suffix = f" _({note})_" if note else ""
            out.append(f"- {marker} **{name}** ({change.ticker}) — {_change_text(change)}{suffix}")
        out.append("")

    out += ["## 종목", ""]
    if not digest.rows:
        out.append("분석된 종목이 없습니다.")
    else:
        out.append("| " + " | ".join(COLUMNS) + " |")
        out.append("| " + " | ".join("---" for _ in COLUMNS) + " |")
        for row in digest.rows:
            out.append("| " + " | ".join(_cells(row)) + " |")

    if digest.failures:
        out += ["", "## 실패", ""]
        for failure in digest.failures:
            out.append(f"- `{failure.ticker}` — {failure.error}")

    out += [
        "",
        "---",
        "",
        "본 리포트의 신호는 과거 데이터와 알고리즘에 근거한 참고 정보입니다. "
        "실제 투자 결과를 보장하지 않으며, 모든 투자 판단과 책임은 사용자 본인에게 있습니다.",
        "",
    ]
    return "\n".join(out)


_CSS = """
:root { color-scheme: light dark; --bg:#fff; --fg:#111; --muted:#666; --line:#e5e5e5;
        --up:#0a7c3f; --down:#c0392b; --card:#fafafa; }
@media (prefers-color-scheme: dark) {
  :root { --bg:#16181c; --fg:#e8e8e8; --muted:#9a9a9a; --line:#2c2f36;
          --up:#4ade80; --down:#f87171; --card:#1d2026; }
}
* { box-sizing: border-box; }
body { margin:0; padding:32px 20px; background:var(--bg); color:var(--fg);
       font: 15px/1.6 -apple-system, "Segoe UI", "Malgun Gothic", sans-serif; }
main { max-width: 940px; margin: 0 auto; }
h1 { font-size: 22px; margin: 0 0 4px; }
h2 { font-size: 15px; margin: 28px 0 10px; color: var(--muted); font-weight: 600; }
.meta { color: var(--muted); font-size: 13px; margin-bottom: 4px; }
.changes { list-style: none; padding: 0; margin: 0; }
.changes li { padding: 8px 12px; background: var(--card); border-radius: 6px; margin-bottom: 6px;
              border-left: 3px solid var(--line); }
.changes li.up { border-left-color: var(--up); }
.changes li.down { border-left-color: var(--down); }
.changes .flip { margin-left: 8px; color: var(--muted); font-size: 12px; white-space: nowrap; }
.table-wrap { overflow-x: auto; }
table { border-collapse: collapse; width: 100%; font-size: 14px; }
th, td { padding: 8px 10px; border-bottom: 1px solid var(--line); text-align: left; white-space: nowrap; }
th { color: var(--muted); font-weight: 600; font-size: 12px; text-transform: uppercase; letter-spacing: .04em; }
td.num { text-align: right; font-variant-numeric: tabular-nums; }
.up { color: var(--up); } .down { color: var(--down); }
.fail { color: var(--down); font-size: 13px; }
footer { margin-top: 32px; padding-top: 14px; border-top: 1px solid var(--line);
         color: var(--muted); font-size: 12px; }
"""


def _cls(value: float) -> str:
    return "up" if value > 0 else "down" if value < 0 else ""


def render_html(
    digest: Digest,
    changes: list[Change] | None = None,
    previous_at: datetime | None = None,
    flips: dict[str, int] | None = None,
) -> str:
    changes = changes or []
    flips = flips or {}
    esc = html.escape
    stamp = digest.generated_at.strftime("%Y-%m-%d")

    parts = [
        "<!doctype html>",
        '<html lang="ko"><head><meta charset="utf-8">',
        '<meta name="viewport" content="width=device-width, initial-scale=1">',
        f"<title>관심종목 리포트 {stamp}</title>",
        f"<style>{_CSS}</style></head><body><main>",
        f"<h1>관심종목 리포트 {stamp}</h1>",
    ]
    parts += [f'<p class="meta">{esc(line)}</p>' for line in _header_lines(digest, previous_at)]

    if changes:
        parts.append("<h2>신호 변화</h2><ul class=\"changes\">")
        for change in changes:
            name = esc(change.name or change.ticker)
            note = _flip_note(change, flips)
            suffix = f'<span class="flip">{esc(note)}</span>' if note else ""
            parts.append(
                f'<li class="{change.direction}"><strong>{name}</strong> '
                f'({esc(change.ticker)}) — {esc(_change_text(change))}{suffix}</li>'
            )
        parts.append("</ul>")

    parts.append("<h2>종목</h2>")
    if not digest.rows:
        parts.append("<p>분석된 종목이 없습니다.</p>")
    else:
        parts.append('<div class="table-wrap"><table><thead><tr>')
        parts += [f"<th>{esc(column)}</th>" for column in COLUMNS]
        parts.append("</tr></thead><tbody>")
        for row in digest.rows:
            cell = _cells(row)
            pnl_class = "" if row.pnl_pct is None else _cls(row.pnl_pct)
            parts.append(
                "<tr>"
                f"<td>{esc(cell[0])}</td>"
                f'<td class="num">{esc(cell[1])}</td>'
                f'<td class="num {_cls(row.change_rate)}">{esc(cell[2])}</td>'
                f"<td>{esc(cell[3])}</td>"
                f'<td class="num">{esc(cell[4])}</td>'
                f"<td>{esc(cell[5])}</td>"
                f'<td class="num {pnl_class}">{esc(cell[6])}</td>'
                "</tr>"
            )
        parts.append("</tbody></table></div>")

    if digest.failures:
        parts.append("<h2>실패</h2>")
        for failure in digest.failures:
            parts.append(f'<p class="fail">{esc(failure.ticker)} — {esc(failure.error)}</p>')

    parts.append(
        "<footer>본 리포트의 신호는 과거 데이터와 알고리즘에 근거한 참고 정보입니다. "
        "실제 투자 결과를 보장하지 않으며, 모든 투자 판단과 책임은 사용자 본인에게 있습니다.</footer>"
    )
    parts.append("</main></body></html>")
    return "\n".join(parts)
