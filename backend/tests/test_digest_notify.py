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


# --- 중복 차단 -----------------------------------------------------------


def test_the_same_change_set_is_not_sent_twice(fake_powershell, tmp_path):
    fake_powershell()
    changes = [_change()]

    first = notify.notify(changes, state_dir=tmp_path)
    second = notify.notify(changes, state_dir=tmp_path)

    assert first.sent is True
    assert (second.sent, second.backend) == (False, "skipped")
    assert "이미 알림" in second.detail


def test_a_different_change_set_still_goes_out(fake_powershell, tmp_path):
    fake_powershell()

    notify.notify([_change()], state_dir=tmp_path)
    second = notify.notify([_change("000660", "SK하이닉스", "BUY", "SELL", "down")], state_dir=tmp_path)

    assert second.sent is True


def test_renotify_is_possible_by_dropping_the_state_dir(fake_powershell, tmp_path):
    fake_powershell()
    changes = [_change()]

    notify.notify(changes, state_dir=tmp_path)

    # CLI 의 --renotify 는 state_dir 을 주지 않는 것으로 구현된다.
    assert notify.notify(changes, state_dir=None).sent is True


def test_a_corrupt_state_file_does_not_block_the_alert(fake_powershell, tmp_path):
    fake_powershell()
    (tmp_path / ".notified.json").write_text("{ broken", encoding="utf-8")

    # 못 보내는 쪽이 더 나쁘다.
    assert notify.notify([_change()], state_dir=tmp_path).sent is True


def test_a_failed_send_is_not_remembered(fake_powershell, tmp_path):
    fake_powershell(returncode=1, stderr="실패")

    notify.notify([_change()], backend="toast", state_dir=tmp_path)

    assert not (tmp_path / ".notified.json").exists()


def test_fingerprint_ignores_order(fake_powershell):
    a = _change("005930", "삼성전자")
    b = _change("000660", "SK하이닉스", "BUY", "SELL", "down")

    assert notify.fingerprint([a, b]) == notify.fingerprint([b, a])


# --- 메일 ---------------------------------------------------------------


@pytest.fixture
def smtp_env(monkeypatch):
    for key, value in {
        "DIGEST_SMTP_HOST": "smtp.example.com",
        "DIGEST_SMTP_PORT": "587",
        "DIGEST_SMTP_USER": "sender@example.com",
        "DIGEST_SMTP_PASSWORD": "app-password",
        "DIGEST_MAIL_TO": "me@example.com",
    }.items():
        monkeypatch.setenv(key, value)


@pytest.fixture
def fake_smtp(monkeypatch):
    """smtplib.SMTP 를 가로챈다. 실제 메일은 나가지 않는다."""
    sent: list[object] = []

    class FakeSMTP:
        def __init__(self, host, port, timeout=None):
            sent.append(("connect", host, port))

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def starttls(self):
            sent.append(("starttls",))

        def login(self, user, password):
            sent.append(("login", user, password))

        def send_message(self, message):
            sent.append(("send", message))

    monkeypatch.setattr(notify.smtplib, "SMTP", FakeSMTP)
    return sent


def test_mail_is_skipped_without_configuration(monkeypatch, tmp_path):
    for key in ("DIGEST_SMTP_HOST", "DIGEST_SMTP_USER", "DIGEST_SMTP_PASSWORD", "DIGEST_MAIL_TO"):
        monkeypatch.delenv(key, raising=False)

    result = notify.notify([_change()], backend="email", state_dir=tmp_path)

    assert result.sent is False
    assert "SMTP 설정이 없습니다" in result.detail
    # 못 보냈으므로 기억하지 않는다 — 설정을 채우면 그 변화로 알림이 온다.
    assert not (tmp_path / ".notified.json").exists()


def test_mail_goes_out_when_configured(smtp_env, fake_smtp, tmp_path):
    result = notify.notify([_change()], backend="email", state_dir=tmp_path)

    assert (result.sent, result.backend) == (True, "email")
    kinds = [entry[0] for entry in fake_smtp]
    assert kinds == ["connect", "starttls", "login", "send"]

    message = fake_smtp[-1][1]
    assert message["To"] == "me@example.com"
    assert "신호 변화 1건" in message["Subject"]
    assert "삼성전자  HOLD → BUY" in message.get_content()
    assert "같은 변화로는 다시 오지 않습니다" in message.get_content()


def test_mail_skips_tls_when_told_to(smtp_env, fake_smtp, monkeypatch, tmp_path):
    monkeypatch.setenv("DIGEST_SMTP_TLS", "false")

    notify.notify([_change()], backend="email", state_dir=tmp_path)

    assert [entry[0] for entry in fake_smtp] == ["connect", "login", "send"]


def test_a_broken_smtp_server_does_not_raise(smtp_env, monkeypatch, tmp_path):
    def explode(*args, **kwargs):
        raise OSError("연결 거부")

    monkeypatch.setattr(notify.smtplib, "SMTP", explode)

    result = notify.notify([_change()], backend="email", state_dir=tmp_path)

    assert result.sent is False
    assert "메일 발송 실패" in result.detail


def test_all_sends_both_channels(smtp_env, fake_smtp, fake_powershell, tmp_path):
    calls = fake_powershell()

    result = notify.notify([_change()], backend="all", state_dir=tmp_path)

    assert (result.sent, result.backend) == (True, "toast+email")
    assert len(calls) == 1
    assert [entry[0] for entry in fake_smtp][-1] == "send"


def test_all_survives_one_channel_failing(smtp_env, fake_smtp, fake_powershell, tmp_path):
    fake_powershell(returncode=1, stderr="토스트 실패")

    result = notify.notify([_change()], backend="all", state_dir=tmp_path)

    assert (result.sent, result.backend) == (True, "email")
