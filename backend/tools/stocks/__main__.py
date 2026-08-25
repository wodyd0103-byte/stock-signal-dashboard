"""관심종목·보유 종목 등록 CLI.

    python -m tools.stocks list
    python -m tools.stocks watch add 삼성전자
    python -m tools.stocks watch rm 005930
    python -m tools.stocks hold add 000660 --qty 3 --avg 150000
    python -m tools.stocks hold rm 000660

서버를 띄우지 않는다. `backend/` 에서 가상환경 파이썬으로 실행한다.
"""
from __future__ import annotations

import argparse
import sys

from app.database import SessionLocal
from app.services.data_provider import DataProviderError
from tools.stocks import registry


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m tools.stocks",
        description="관심종목·보유 종목을 서버 없이 등록한다. digest가 이 목록을 읽는다.",
    )
    sub = parser.add_subparsers(dest="group", required=True)

    sub.add_parser("list", help="관심종목과 보유 종목을 모두 보여준다")

    watch = sub.add_parser("watch", help="관심종목").add_subparsers(dest="action", required=True)
    watch_add = watch.add_parser("add", help="추가 (이미 있으면 그대로 둔다)")
    watch_add.add_argument("query", help="티커 또는 종목명 (예: 005930, 삼성전자, AAPL)")
    watch_add.add_argument("--name", help="종목명을 직접 지정")
    watch_rm = watch.add_parser("rm", help="삭제")
    watch_rm.add_argument("query")
    watch.add_parser("list", help="관심종목만 보기")

    hold = sub.add_parser("hold", help="보유 종목").add_subparsers(dest="action", required=True)
    hold_add = hold.add_parser("add", help="추가 (이미 있으면 재매수 평균으로 합친다)")
    hold_add.add_argument("query")
    hold_add.add_argument("--qty", type=float, required=True, help="수량")
    hold_add.add_argument("--avg", type=float, required=True, help="평균 매입가")
    hold_add.add_argument("--name")
    hold_add.add_argument("--replace", action="store_true", help="합치지 않고 수량·평단을 덮어쓴다")
    hold_rm = hold.add_parser("rm", help="삭제")
    hold_rm.add_argument("query")
    hold.add_parser("list", help="보유 종목만 보기")

    return parser


def _print_watch(items) -> None:
    print(f"관심종목 {len(items)}건")
    for item in items:
        print(f"  {item.ticker}  {item.name or '-'}")


def _print_hold(items) -> None:
    print(f"보유 종목 {len(items)}건")
    for item in items:
        print(f"  {item.ticker}  {item.name or '-'}  {item.quantity:g}주 @ {item.avg_price:,.0f}")


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    db = SessionLocal()
    try:
        if args.group == "list":
            _print_watch(registry.list_watch(db))
            print()
            _print_hold(registry.list_hold(db))
            return 0

        if args.action == "list":
            if args.group == "watch":
                _print_watch(registry.list_watch(db))
            else:
                _print_hold(registry.list_hold(db))
            return 0

        try:
            resolved = registry.resolve(args.query)
        except DataProviderError as exc:
            print(f"티커를 해석할 수 없습니다: {exc}", file=sys.stderr)
            return 2

        name = getattr(args, "name", None) or resolved.name
        label = f"{resolved.ticker}" + (f" ({name})" if name else "")

        if args.group == "watch":
            if args.action == "add":
                _, created = registry.add_watch(db, resolved.ticker, name)
                print(f"{'추가' if created else '이미 등록됨'}: 관심종목 {label}")
                return 0
            if not registry.remove_watch(db, resolved.ticker):
                print(f"관심종목에 없습니다: {resolved.ticker}", file=sys.stderr)
                return 1
            print(f"삭제: 관심종목 {label}")
            return 0

        if args.action == "add":
            if args.qty <= 0 or args.avg <= 0:
                print("수량과 평균 매입가는 0보다 커야 합니다.", file=sys.stderr)
                return 2
            item, created = registry.add_hold(
                db, resolved.ticker, args.qty, args.avg, name, replace=args.replace
            )
            verb = "추가" if created else ("덮어씀" if args.replace else "합산")
            print(f"{verb}: 보유 {label}  {item.quantity:g}주 @ {item.avg_price:,.0f}")
            return 0

        if not registry.remove_hold(db, resolved.ticker):
            print(f"보유 종목에 없습니다: {resolved.ticker}", file=sys.stderr)
            return 1
        print(f"삭제: 보유 {label}")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
