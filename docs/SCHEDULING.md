# 일일 리포트 자동 실행

`digest-scheduled.bat`을 Windows 작업 스케줄러에 걸어 아침마다 리포트를 뽑는 방법입니다.
등록 명령은 아래에 있지만, **실행은 직접 하세요.** 작업 스케줄러 등록은 시스템 설정 변경입니다.

## 두 배치 파일의 차이

| 파일 | 용도 | 차이 |
| --- | --- | --- |
| `digest.bat` | 사람이 더블클릭 | HTML을 브라우저로 열고, 실패하면 `pause`로 창을 붙잡는다 |
| `digest-scheduled.bat` | 작업 스케줄러 | 브라우저를 열지 않고 `pause`도 하지 않는다 |

자동 실행에 `digest.bat`을 걸면 자리에 없을 때 브라우저가 뜨고, 실패 시 `pause`가 걸려
작업이 끝나지 않은 상태로 남습니다.

## 등록

평일 08:10에 실행하는 예입니다. 경로는 저장소 위치에 맞게 바꾸세요.

```bat
schtasks /Create /TN "QuantInsight Digest" /TR "\"C:\Users\sts07\OneDrive\Desktop\workspace\QUANT\digest-scheduled.bat\"" /SC WEEKLY /D MON,TUE,WED,THU,FRI /ST 08:10 /F
```

- `/F` — 같은 이름의 작업이 있으면 덮어씁니다.
- 경로에 공백이 있으므로 `/TR` 값 안쪽 따옴표(`\"`)가 필요합니다.
- 노트북을 닫아두는 시간대라면 GUI(`taskschd.msc`)에서 "가장 빠른 시간에 놓친 작업 실행"을
  켜두는 편이 낫습니다. `schtasks`로는 이 옵션을 지정할 수 없습니다.

## 확인

등록됐는지:

```bat
schtasks /Query /TN "QuantInsight Digest" /V /FO LIST
```

기다리지 않고 지금 한 번 돌려보기:

```bat
schtasks /Run /TN "QuantInsight Digest"
```

결과는 `backend/data/digest/`에 그날 날짜로 `.md`, `.html`, `.json`이 생겼는지로 확인합니다.
신호가 바뀐 종목이 있으면 알림이 나갑니다. 바뀐 게 없으면 알림은 오지 않습니다 — 정상 동작입니다.

알림이 시끄러우면 `digest-scheduled.bat`의 `--notify` 를 빼세요. 리포트 파일은 그대로 쌓이고
알림만 멈춥니다. 같은 변화로 두 번 알림이 오는 일은 없습니다 — 보낸 내용의 지문을
`backend/data/digest/.notified.json`에 남겨 두고 비교합니다.

## 실패 확인

`Last Result`가 0이 아니면 실패입니다.

```bat
schtasks /Query /TN "QuantInsight Digest" /FO LIST /V | findstr /C:"Last Result" /C:"Last Run Time"
```

| 코드 | 뜻 |
| --- | --- |
| 0 | 정상 |
| 1 | 대상 종목을 전부 분석하지 못했다 (네트워크·제공자 장애) |
| 9 | 가상환경(`backend/.venv`)이 없다. `start.bat`을 한 번 실행하세요 |

며칠째 조용하면 알림이 안 오는 것인지 작업이 안 도는 것인지 헷갈립니다. `Last Run Time`을
먼저 보세요.

## 해제

```bat
schtasks /Delete /TN "QuantInsight Digest" /F
```

## 주의

- 작업 스케줄러는 **로그인 세션과 무관하게** 돌 수 있습니다. 토스트 알림은 로그인한 사용자
  세션에서만 보이므로, "사용자가 로그온한 경우에만 실행"으로 두는 편이 알림 목적에 맞습니다.
- 리포트에는 보유 수량과 평단가가 들어갑니다. 출력 디렉터리는 `.gitignore`에 있지만,
  공용 PC라면 `--out`으로 다른 위치를 지정하세요.
