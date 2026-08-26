"""신호 변화 알림.

외부 패키지를 쓰지 않는다. Windows 10 이상이면 PowerShell로 WinRT 토스트를 띄우고,
안 되면 콘솔로 떨어진다. BurntToast 같은 모듈 설치를 요구하면 스케줄러에 걸어둔 뒤
환경이 바뀌었을 때 조용히 죽는다.

**변화가 있을 때만, 그리고 같은 변화로는 한 번만 보낸다.** 변화 없는 날에도 알림이 오면
며칠 만에 무시하게 되고, 그때부터 알림은 없는 것과 같다. 같은 이유로 하루에 digest를 두 번
돌렸다고 같은 알림이 두 번 오지 않는다 — 보낸 내용의 지문을 남겨 두고 비교한다.
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import smtplib
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime
from email.message import EmailMessage
from pathlib import Path
from xml.sax.saxutils import escape

from tools.digest.store import Change

# PowerShell 자체의 AUMID. 별도 앱 등록 없이 토스트를 띄울 수 있는 가장 흔한 방법이다.
_APP_ID = r"{1AC14E77-02E7-4E5D-B744-2EB1AE5198B7}\WindowsPowerShell\v1.0\powershell.exe"

_MAX_LINES = 4
_TIMEOUT_SECONDS = 15


@dataclass
class Result:
    sent: bool
    backend: str  # "toast" | "console" | "skipped"
    detail: str = ""


def summarise(changes: list[Change]) -> tuple[str, list[str]]:
    """토스트 한 장에 들어갈 제목과 본문 줄."""
    grades = sum(1 for change in changes if change.is_signal)
    if grades and grades != len(changes):
        title = f"신호 변화 {grades}건 · 점수 이동 {len(changes) - grades}건"
    elif grades:
        title = f"신호 변화 {grades}건"
    else:
        title = f"점수 이동 {len(changes)}건"

    labels = {"score": "매수점수 ", "risk": "리스크 "}
    lines = []
    for change in changes[:_MAX_LINES]:
        name = change.name or change.ticker
        if change.is_new:
            body = f"신규 {change.current}"
        else:
            body = f"{labels.get(change.kind, '')}{change.previous} → {change.current}"
        lines.append(f"{name}  {body}")
    if len(changes) > _MAX_LINES:
        lines.append(f"외 {len(changes) - _MAX_LINES}건")
    return title, lines


def build_toast_xml(title: str, lines: list[str]) -> str:
    """종목명과 신호는 외부 데이터다. XML로 넣기 전에 escape 한다."""
    body = escape("\n".join(lines))
    return (
        '<toast><visual><binding template="ToastGeneric">'
        f"<text>{escape(title)}</text>"
        f"<text>{body}</text>"
        "</binding></visual></toast>"
    )


def _powershell_script(xml: str) -> str:
    """XML을 base64로 넘긴다. 따옴표·줄바꿈이 섞인 값을 명령줄에 직접 끼우지 않는다."""
    payload = base64.b64encode(xml.encode("utf-8")).decode("ascii")
    return (
        "[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, "
        "ContentType=WindowsRuntime] > $null; "
        "[Windows.Data.Xml.Dom.XmlDocument, Windows.Data.Xml.Dom, ContentType=WindowsRuntime] > $null; "
        f"$raw = [Text.Encoding]::UTF8.GetString([Convert]::FromBase64String('{payload}')); "
        "$doc = New-Object Windows.Data.Xml.Dom.XmlDocument; "
        "$doc.LoadXml($raw); "
        "$toast = New-Object Windows.UI.Notifications.ToastNotification $doc; "
        f"[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier('{_APP_ID}').Show($toast)"
    )


def _send_toast(title: str, lines: list[str]) -> Result:
    if os.name != "nt":
        return Result(False, "console", "Windows가 아닙니다.")

    script = _powershell_script(build_toast_xml(title, lines))
    try:
        completed = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
            capture_output=True,
            text=True,
            timeout=_TIMEOUT_SECONDS,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return Result(False, "console", f"PowerShell 실행 실패: {exc}")

    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout or "").strip().splitlines()
        return Result(False, "console", detail[0] if detail else f"종료코드 {completed.returncode}")
    return Result(True, "toast")


def _print_console(title: str, lines: list[str]) -> None:
    print(f"[알림] {title}")
    for line in lines:
        print(f"  {line}")


# --- 중복 차단 ---------------------------------------------------------


def fingerprint(changes: list[Change]) -> str:
    """이 변화 묶음의 지문. 같은 전환 조합이면 같은 값이 나온다."""
    parts = sorted(f"{c.kind}:{c.ticker}:{c.previous or ''}>{c.current}" for c in changes)
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()[:16]


def _state_path(directory: Path) -> Path:
    return directory / ".notified.json"


def already_sent(changes: list[Change], directory: Path | None) -> bool:
    """직전에 보낸 것과 같은 묶음인가."""
    if directory is None:
        return False
    path = _state_path(directory)
    if not path.exists():
        return False
    try:
        stored = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        # 상태 파일이 깨졌다고 알림을 막지는 않는다. 못 보내는 쪽이 더 나쁘다.
        return False
    return stored.get("fingerprint") == fingerprint(changes)


def remember(changes: list[Change], directory: Path | None) -> None:
    if directory is None:
        return
    try:
        directory.mkdir(parents=True, exist_ok=True)
        _state_path(directory).write_text(
            json.dumps(
                {
                    "fingerprint": fingerprint(changes),
                    "sent_at": datetime.now().isoformat(timespec="seconds"),
                    "count": len(changes),
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
    except OSError:
        # 기록에 실패해도 알림 자체는 이미 나갔다. 다음 실행에서 한 번 더 올 뿐이다.
        pass


# --- 메일 -------------------------------------------------------------


@dataclass
class MailConfig:
    host: str
    port: int
    user: str
    password: str
    sender: str
    recipient: str
    use_tls: bool


def mail_config() -> MailConfig | None:
    """`.env` 에 SMTP 설정이 있을 때만 메일을 쓴다. 없으면 None."""
    host = os.getenv("DIGEST_SMTP_HOST", "").strip()
    user = os.getenv("DIGEST_SMTP_USER", "").strip()
    password = os.getenv("DIGEST_SMTP_PASSWORD", "").strip()
    recipient = os.getenv("DIGEST_MAIL_TO", "").strip()
    if not (host and user and password and recipient):
        return None
    return MailConfig(
        host=host,
        port=int(os.getenv("DIGEST_SMTP_PORT", "587")),
        user=user,
        password=password,
        sender=os.getenv("DIGEST_MAIL_FROM", "").strip() or user,
        recipient=recipient,
        use_tls=os.getenv("DIGEST_SMTP_TLS", "true").strip().lower() not in {"0", "false", "no", "off"},
    )


def build_message(config: MailConfig, title: str, lines: list[str]) -> EmailMessage:
    message = EmailMessage()
    message["Subject"] = f"[Quant Insight] {title}"
    message["From"] = config.sender
    message["To"] = config.recipient
    body = "\n".join(lines)
    message.set_content(
        f"{title}\n\n{body}\n\n"
        "이 메일은 신호가 바뀐 날에만 발송됩니다. 같은 변화로는 다시 오지 않습니다.\n"
        "본 신호는 과거 데이터와 알고리즘에 근거한 참고 정보이며 투자 결과를 보장하지 않습니다.\n"
    )
    return message


def _send_mail(title: str, lines: list[str]) -> Result:
    config = mail_config()
    if config is None:
        return Result(
            False,
            "console",
            "SMTP 설정이 없습니다. backend/.env 에 DIGEST_SMTP_HOST/USER/PASSWORD/MAIL_TO 를 넣으세요.",
        )

    try:
        with smtplib.SMTP(config.host, config.port, timeout=_TIMEOUT_SECONDS) as server:
            if config.use_tls:
                server.starttls()
            server.login(config.user, config.password)
            server.send_message(build_message(config, title, lines))
    except Exception as exc:
        return Result(False, "console", f"메일 발송 실패: {exc}")
    return Result(True, "email")


# --- 진입점 -----------------------------------------------------------


def notify(changes: list[Change], backend: str = "auto", state_dir: Path | None = None) -> Result:
    """변화가 있을 때만, 같은 변화로는 한 번만 보낸다.

    backend: auto(토스트, 실패 시 콘솔) | toast | email | all(토스트+메일) | console | off
    state_dir 를 주면 직전에 보낸 묶음과 비교해 중복 발송을 막는다.
    """
    if not changes:
        return Result(False, "skipped", "변화 없음")
    if backend == "off":
        return Result(False, "skipped", "알림 꺼짐")
    if already_sent(changes, state_dir):
        return Result(False, "skipped", "같은 변화로 이미 알림을 보냈습니다")

    title, lines = summarise(changes)

    if backend == "console":
        _print_console(title, lines)
        remember(changes, state_dir)
        return Result(True, "console")

    if backend == "email":
        result = _send_mail(title, lines)
        if result.sent:
            remember(changes, state_dir)
        return result

    if backend == "all":
        toast = _send_toast(title, lines)
        mail = _send_mail(title, lines)
        if toast.sent or mail.sent:
            remember(changes, state_dir)
            detail = " / ".join(filter(None, [toast.detail, mail.detail]))
            return Result(True, "toast+email" if toast.sent and mail.sent else ("toast" if toast.sent else "email"), detail)
        return Result(False, "console", " / ".join(filter(None, [toast.detail, mail.detail])))

    result = _send_toast(title, lines)
    if result.sent:
        remember(changes, state_dir)
        return result
    if backend == "toast":
        return result

    # auto: 토스트가 안 되면 최소한 콘솔에는 남긴다.
    _print_console(title, lines)
    print(f"  (토스트 실패: {result.detail})", file=sys.stderr)
    remember(changes, state_dir)
    return Result(True, "console", result.detail)
