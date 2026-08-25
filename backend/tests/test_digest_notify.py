"""알림 테스트 — 실제 토스트는 띄우지 않는다."""
from __future__ import annotations

import base64
import subprocess

import pytest

from tools.digest import notify
from tools.digest.store import Change


def _change(ticker="005930", name="삼성전자", previous="HOLD", current="BUY", direction="up") -> Change:
    return Change(ticker, name, previous, current, direction)


@pytest.fixture
def fake_powershell(monkeypatch):
    """subprocess.run 을 가로채 호출 인자를 붙잡는다."""
    calls: list[list[str]] = []

    def _install(returncode=0, stderr="", raises=None):
        def fake_run(cmd, **kwargs):
            calls.append(cmd)
            if raises:
                raise raises
            return subprocess.CompletedProcess(cmd, returncode, stdout="", stderr=stderr)

        monkeypatch.setattr(notify.subprocess, "run", fake_run)
        monkeypatch.setattr(notify.os, "name", "nt")
        return calls

    return _install


# --- 요약 ----------------------------------------------------------------


def test_summarise_lists_each_change(fake_powershell):
    title, lines = notify.summarise([_change(), _change("000660", "SK하이닉스", "BUY", "HOLD", "down")])

    assert title == "신호 변화 2건"
    assert lines == ["삼성전자  HOLD → BUY", "SK하이닉스  BUY → HOLD"]


def test_summarise_collapses_a_long_list():
    changes = [_change(f"00{i}", f"종목{i}") for i in range(7)]

    _, lines = notify.summarise(changes)

    assert len(lines) == notify._MAX_LINES + 1
    assert lines[-1] == "외 3건"


def test_summarise_marks_a_new_ticker():
    _, lines = notify.summarise([Change("005930", "삼성전자", None, "BUY", "new")])
    assert lines == ["삼성전자  신규 BUY"]


# --- XML -----------------------------------------------------------------


def test_toast_xml_escapes_the_stock_name():
    # 종목명은 외부 데이터다. XML 구조를 깨뜨리면 안 된다.
    xml = notify.build_toast_xml("제목", ["<b>&이상한</b> 이름"])

    assert "<b>" not in xml.split("<text>제목</text>")[1]
    assert "&lt;b&gt;&amp;이상한" in xml


def test_the_script_carries_the_xml_as_base64(fake_powershell):
    calls = fake_powershell()

    notify.notify([_change()])

    script = calls[0][-1]
    payload = script.split("FromBase64String('")[1].split("')")[0]
    decoded = base64.b64decode(payload).decode("utf-8")
    assert "삼성전자" in decoded
    # 따옴표가 섞인 값이 명령줄에 직접 들어가지 않는다.
    assert "삼성전자" not in script


# --- 동작 ----------------------------------------------------------------


def test_nothing_is_sent_without_changes(fake_powershell):
    calls = fake_powershell()

    result = notify.notify([])

    assert (result.sent, result.backend) == (False, "skipped")
    assert calls == []


def test_off_sends_nothing(fake_powershell):
    calls = fake_powershell()

    assert notify.notify([_change()], backend="off").sent is False
    assert calls == []


def test_toast_success(fake_powershell):
    fake_powershell(returncode=0)

    result = notify.notify([_change()])

    assert (result.sent, result.backend) == (True, "toast")


def test_auto_falls_back_to_console(fake_powershell, capsys):
    fake_powershell(returncode=1, stderr="토스트 실패 이유")

    result = notify.notify([_change()], backend="auto")

    captured = capsys.readouterr()
    assert (result.sent, result.backend) == (True, "console")
    assert "신호 변화 1건" in captured.out
    assert "토스트 실패 이유" in captured.err


def test_toast_backend_does_not_fall_back(fake_powershell, capsys):
    fake_powershell(returncode=1, stderr="실패")

    result = notify.notify([_change()], backend="toast")

    assert (result.sent, result.backend) == (False, "console")
    assert capsys.readouterr().out == ""


def test_a_powershell_crash_is_caught(fake_powershell, capsys):
    fake_powershell(raises=OSError("powershell 없음"))

    result = notify.notify([_change()], backend="auto")

    assert result.sent is True and result.backend == "console"
    assert "powershell 없음" in capsys.readouterr().err


def test_console_backend_skips_powershell(fake_powershell, capsys):
    calls = fake_powershell()

    result = notify.notify([_change()], backend="console")

    assert (result.sent, result.backend) == (True, "console")
    assert calls == []
    assert "삼성전자" in capsys.readouterr().out


def test_non_windows_uses_the_console(monkeypatch, capsys):
    monkeypatch.setattr(notify.os, "name", "posix")

    result = notify.notify([_change()], backend="auto")

    assert result.backend == "console"
    assert "Windows가 아닙니다" in capsys.readouterr().err
