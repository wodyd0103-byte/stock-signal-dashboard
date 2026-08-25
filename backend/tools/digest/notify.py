"""신호 변화 알림.

외부 패키지를 쓰지 않는다. Windows 10 이상이면 PowerShell로 WinRT 토스트를 띄우고,
안 되면 콘솔로 떨어진다. BurntToast 같은 모듈 설치를 요구하면 스케줄러에 걸어둔 뒤
환경이 바뀌었을 때 조용히 죽는다.

**변화가 있을 때만 보낸다.** 변화 없는 날에도 알림이 오면 며칠 만에 무시하게 되고,
그때부터 알림은 없는 것과 같다.
"""
from __future__ import annotations

import base64
import os
import subprocess
import sys
from dataclasses import dataclass
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
    title = f"신호 변화 {len(changes)}건"
    lines = []
    for change in changes[:_MAX_LINES]:
        name = change.name or change.ticker
        body = f"신규 {change.current}" if change.is_new else f"{change.previous} → {change.current}"
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


def notify(changes: list[Change], backend: str = "auto") -> Result:
    """변화가 없으면 아무것도 보내지 않는다.

    backend: auto(토스트 시도 후 실패 시 콘솔) | toast(실패해도 콘솔로 안 떨어짐) | console | off
    """
    if not changes or backend == "off":
        return Result(False, "skipped", "변화 없음" if not changes else "알림 꺼짐")

    title, lines = summarise(changes)

    if backend == "console":
        _print_console(title, lines)
        return Result(True, "console")

    result = _send_toast(title, lines)
    if result.sent or backend == "toast":
        return result

    # auto: 토스트가 안 되면 최소한 콘솔에는 남긴다.
    _print_console(title, lines)
    print(f"  (토스트 실패: {result.detail})", file=sys.stderr)
    return Result(True, "console", result.detail)
