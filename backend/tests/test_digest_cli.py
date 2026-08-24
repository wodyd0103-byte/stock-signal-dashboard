"""digest CLI 테스트 — 분석은 대역으로 막고 배선만 본다."""
from __future__ import annotations

import argparse
import json
from datetime import datetime

import pytest

from tools.digest import __main__ as cli
from tools.digest.collector import Digest, Failure, Row


def _digest(rows=None, failures=None) -> Digest:
    return Digest(
        generated_at=datetime(2026, 8, 25, 8, 30),
        period="1y",
        rows=rows if rows is not None else [
            Row(
                ticker="005930", name="삼성전자", sources=["watchlist"],
                current_price=60_000.0, change_rate=1.5, signal="BUY",
                buy_score=70, sell_score=10, risk_score=30, risk_level="보통",
                final_buy_score=70, market_regime="SIDEWAYS", ml_up_probability=0.6,
                reasons=["테스트"],
            )
        ],
        failures=failures or [],
    )


@pytest.fixture
def stub_collect(monkeypatch):
    def _install(digest: Digest):
        monkeypatch.setattr(cli.collector, "collect", lambda **kwargs: digest)
        return digest

    return _install


def test_source_parsing_rejects_an_unknown_value():
    assert cli._parse_sources("watchlist,holdings") == ["watchlist", "holdings"]
    with pytest.raises(argparse.ArgumentTypeError):
        cli._parse_sources("watchlist,없는것")


def test_run_writes_markdown_html_and_a_snapshot(stub_collect, tmp_path, capsys):
    stub_collect(_digest())

    code = cli.main(["--md", "--html", "--out", str(tmp_path)])

    assert code == 0
    names = sorted(p.name for p in tmp_path.iterdir())
    assert names == ["2026-08-25.html", "2026-08-25.json", "2026-08-25.md"]
    assert "삼성전자" in capsys.readouterr().out


def test_no_save_skips_the_snapshot(stub_collect, tmp_path):
    stub_collect(_digest())

    cli.main(["--no-save", "--out", str(tmp_path)])

    assert not list(tmp_path.glob("*.json"))


def test_second_run_compares_against_the_first(stub_collect, tmp_path, capsys):
    stub_collect(_digest())
    cli.main(["--out", str(tmp_path)])
    capsys.readouterr()

    # 어제 파일로 돌려놓고 신호를 낮춘 채 다시 돌린다.
    (tmp_path / "2026-08-25.json").rename(tmp_path / "2026-08-24.json")
    downgraded = _digest()
    downgraded.rows[0].signal = "HOLD"
    stub_collect(downgraded)

    cli.main(["--out", str(tmp_path)])

    out = capsys.readouterr().out
    assert "신호 변화" in out
    assert "BUY → HOLD" in out


def test_colour_is_stripped_when_asked(stub_collect, tmp_path, capsys):
    stub_collect(_digest())

    cli.main(["--colour", "never", "--out", str(tmp_path)])

    assert "\033[" not in capsys.readouterr().out


def test_exit_code_is_one_when_everything_failed(stub_collect, tmp_path):
    stub_collect(_digest(rows=[], failures=[Failure("005930", "삼성전자", ["watchlist"], "죽음")]))

    assert cli.main(["--out", str(tmp_path)]) == 1


def test_snapshot_keeps_the_rows_for_the_next_comparison(stub_collect, tmp_path):
    stub_collect(_digest())

    cli.main(["--out", str(tmp_path)])

    payload = json.loads((tmp_path / "2026-08-25.json").read_text(encoding="utf-8"))
    assert payload["rows"][0]["signal"] == "BUY"
