"""digest CLI 진입점.

    python -m tools.digest --md --html --open

서버를 띄우지 않는다. `backend/` 에서 가상환경 파이썬으로 실행한다.
"""
from __future__ import annotations

import argparse
import os
import re
import sys
import webbrowser
from pathlib import Path

from app.database import SessionLocal
from tools.digest import collector, history, render, store

PERIODS = ("1mo", "3mo", "6mo", "1y", "3y")
SOURCES = ("watchlist", "holdings")

_ANSI = re.compile(r"\033\[[0-9;]*m")


def _enable_windows_ansi() -> None:
    """Windows 콘솔에서 ANSI 색상을 켠다. 실패해도 색만 빠지고 동작은 같다."""
    if os.name != "nt":
        return
    try:
        import ctypes

        kernel32 = ctypes.windll.kernel32
        kernel32.SetConsoleMode(kernel32.GetStdHandle(-11), 7)
    except Exception:
        pass


def _use_colour(flag: str) -> bool:
    if flag == "never":
        return False
    if flag == "always":
        return True
    # 파이프로 넘기거나 파일로 리다이렉트하면 제어문자가 섞여 읽기 나빠진다.
    return sys.stdout.isatty() and not os.getenv("NO_COLOR")


def _parse_sources(raw: str) -> list[str]:
    values = [item.strip() for item in raw.split(",") if item.strip()]
    unknown = [value for value in values if value not in SOURCES]
    if unknown:
        raise argparse.ArgumentTypeError(f"알 수 없는 source: {', '.join(unknown)} (가능: {', '.join(SOURCES)})")
    return values or list(SOURCES)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m tools.digest",
        description="관심종목·보유종목 일일 리포트. 서버 없이 돈다.",
    )
    parser.add_argument("--source", type=_parse_sources, default=list(SOURCES),
                        help="watchlist,holdings 중 콤마로 (기본: 둘 다)")
    parser.add_argument("--period", choices=PERIODS, default="1y", help="분석 기간 (기본: 1y)")
    parser.add_argument("--md", action="store_true", help="마크다운 파일로 저장")
    parser.add_argument("--html", action="store_true", help="HTML 파일로 저장")
    parser.add_argument("--open", action="store_true", help="저장한 HTML을 브라우저로 열기 (--html 필요)")
    parser.add_argument("--out", type=Path, default=store.DEFAULT_DIR, help="출력 디렉터리")
    parser.add_argument("--no-save", action="store_true", help="스냅샷을 남기지 않는다 (다음 실행의 비교 대상이 안 됨)")
    parser.add_argument("--workers", type=int, default=collector.MAX_WORKERS, help="동시 분석 수")
    parser.add_argument("--timeout", type=int, default=collector.ITEM_TIMEOUT_SECONDS, help="종목당 제한 시간(초)")
    parser.add_argument("--colour", "--color", dest="colour", choices=("auto", "always", "never"), default="auto")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    _enable_windows_ansi()

    digest = collector.collect(
        sources=args.source,
        period=args.period,
        max_workers=max(1, args.workers),
        item_timeout=max(1, args.timeout),
    )

    previous = store.load_previous(args.out, before=digest.generated_at.date())
    changes = store.diff_signals(digest, previous)
    previous_at = store.previous_generated_at(previous)

    text = render.render_terminal(digest, changes, previous_at)
    print(text if _use_colour(args.colour) else _ANSI.sub("", text))

    written: list[Path] = []
    stamp = digest.generated_at.date().isoformat()

    if args.md:
        path = args.out / f"{stamp}.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(render.render_markdown(digest, changes, previous_at), encoding="utf-8")
        written.append(path)

    html_path: Path | None = None
    if args.html:
        html_path = args.out / f"{stamp}.html"
        html_path.parent.mkdir(parents=True, exist_ok=True)
        html_path.write_text(render.render_html(digest, changes, previous_at), encoding="utf-8")
        written.append(html_path)

    if not args.no_save:
        written.append(store.save_snapshot(digest, args.out))

        db = SessionLocal()
        try:
            inserted = history.record(db, digest, changes)
        finally:
            db.close()
        if inserted:
            print(f"신호 변화 {inserted}건을 이력에 기록했습니다.")

    for path in written:
        print(f"저장: {path}")

    if args.open:
        if html_path:
            webbrowser.open(html_path.resolve().as_uri())
        else:
            print("--open 은 --html 과 같이 써야 합니다.", file=sys.stderr)

    # 전 종목이 실패하면 종료코드로 알린다. 스케줄러에 걸었을 때 조용히 넘어가지 않게.
    if digest.failures and not digest.rows:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
