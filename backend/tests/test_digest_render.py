"""digest 스냅샷/비교/출력 테스트."""
from __future__ import annotations

import json
from datetime import date, datetime

import pytest

from tools.digest import render, store
from tools.digest.collector import Digest, Failure, Row


def _row(ticker: str, name: str, signal: str, *, price=60_000.0, change=1.5, buy=50, pnl=None) -> Row:
    return Row(
        ticker=ticker,
        name=name,
        sources=["watchlist"],
        current_price=price,
        change_rate=change,
        signal=signal,
        buy_score=buy,
        sell_score=10,
        risk_score=30,
        risk_level="보통",
        final_buy_score=buy,
        market_regime="SIDEWAYS",
        ml_up_probability=0.5,
        reasons=["테스트 사유"],
        pnl_pct=pnl,
    )


@pytest.fixture
def digest() -> Digest:
    return Digest(
        generated_at=datetime(2026, 8, 25, 8, 30),
        period="1y",
        rows=[
            _row("000660", "SK하이닉스", "BUY", pnl=12.5),
            _row("005930", "삼성전자", "HOLD", change=-2.0, pnl=-8.0),
        ],
        failures=[Failure(ticker="035720", name="카카오", sources=["holdings"], error="provider 죽음")],
        market_sentiment={"score": 55, "label": "중립"},
    )


# --- store ---------------------------------------------------------------


def test_snapshot_round_trips(digest, tmp_path):
    path = store.save_snapshot(digest, tmp_path)

    assert path.name == "2026-08-25.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert [row["ticker"] for row in payload["rows"]] == ["000660", "005930"]
    assert payload["failures"][0]["ticker"] == "035720"


def test_load_previous_picks_the_latest_before_today(digest, tmp_path):
    (tmp_path / "2026-08-20.json").write_text(json.dumps({"rows": [], "generated_at": "old"}), encoding="utf-8")
    (tmp_path / "2026-08-22.json").write_text(json.dumps({"rows": [], "generated_at": "newer"}), encoding="utf-8")
    (tmp_path / "2026-08-25.json").write_text(json.dumps({"rows": [], "generated_at": "today"}), encoding="utf-8")

    previous = store.load_previous(tmp_path, before=date(2026, 8, 25))

    # 오늘 파일은 비교 대상이 아니고, "어제"가 아니라 마지막으로 돌린 날과 비교한다.
    assert previous["generated_at"] == "newer"


def test_load_previous_returns_none_without_history(tmp_path):
    assert store.load_previous(tmp_path, before=date(2026, 8, 25)) is None


def test_load_previous_survives_a_corrupt_file(tmp_path):
    (tmp_path / "2026-08-22.json").write_text("{ broken", encoding="utf-8")
    assert store.load_previous(tmp_path, before=date(2026, 8, 25)) is None


def test_diff_reports_only_what_moved(digest):
    previous = {
        "generated_at": "2026-08-22T08:30:00",
        "rows": [
            {"ticker": "000660", "signal": "HOLD"},
            {"ticker": "005930", "signal": "HOLD"},
        ],
    }

    changes = store.diff_signals(digest, previous)

    assert [(c.ticker, c.previous, c.current, c.direction) for c in changes] == [
        ("000660", "HOLD", "BUY", "up")
    ]


def test_diff_marks_a_ticker_absent_from_the_previous_run_as_new(digest):
    changes = store.diff_signals(digest, {"rows": [{"ticker": "005930", "signal": "HOLD"}]})

    assert [(c.ticker, c.direction, c.is_new) for c in changes] == [("000660", "new", True)]


def test_diff_sorts_upgrades_before_downgrades(digest):
    previous = {
        "rows": [
            {"ticker": "000660", "signal": "HOLD"},
            {"ticker": "005930", "signal": "BUY"},
        ]
    }

    changes = store.diff_signals(digest, previous)

    assert [c.direction for c in changes] == ["up", "down"]


def test_diff_is_empty_without_a_previous_run(digest):
    assert store.diff_signals(digest, None) == []


# --- render --------------------------------------------------------------


def test_terminal_output_lists_every_row_and_failure(digest):
    text = render.render_terminal(digest)

    assert "SK하이닉스 (000660)" in text
    assert "삼성전자 (005930)" in text
    assert "035720" in text and "provider 죽음" in text
    assert "시장심리 55/100 (중립)" in text


def test_terminal_columns_line_up_with_wide_characters(digest):
    text = render.render_terminal(digest)
    body = [line for line in text.split("\n") if "(000660)" in line or "(005930)" in line]

    # ANSI 시퀀스를 걷어낸 표시 폭이 같아야 정렬이 맞는 것이다.
    import re

    widths = {render._width(re.sub(r"\033\[[0-9;]*m", "", line)) for line in body}
    assert len(widths) == 1


def test_markdown_has_a_table_and_a_disclaimer(digest):
    text = render.render_markdown(digest)

    assert "| 종목 |" in text
    assert text.count("\n| ") >= 2
    assert "투자 판단과 책임은 사용자 본인에게" in text


def test_html_escapes_the_error_text(digest):
    digest.failures[0].error = "<script>alert(1)</script>"

    markup = render.render_html(digest)

    assert "<script>alert(1)</script>" not in markup
    assert "&lt;script&gt;" in markup


def test_renderers_note_the_signal_changes(digest):
    changes = store.diff_signals(digest, {"rows": [{"ticker": "000660", "signal": "HOLD"}]})

    assert "신호 변화" in render.render_terminal(digest, changes)
    assert "신호 변화" in render.render_markdown(digest, changes)
    assert "신호 변화" in render.render_html(digest, changes)


def test_renderers_handle_an_empty_digest():
    empty = Digest(generated_at=datetime(2026, 8, 25, 8, 30), period="1y", rows=[], failures=[])

    for text in (render.render_terminal(empty), render.render_markdown(empty), render.render_html(empty)):
        assert "분석된 종목이 없습니다" in text


def test_previous_generated_at_parses_the_stamp():
    assert store.previous_generated_at({"generated_at": "2026-08-22T08:30:00"}) == datetime(2026, 8, 22, 8, 30)
    assert store.previous_generated_at({"generated_at": "쓰레기"}) is None
    assert store.previous_generated_at(None) is None
