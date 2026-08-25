@echo off
REM 관심종목 일일 리포트 — 서버 없이 분석하고 HTML을 띄운다.
REM 더블클릭하거나, 작업 스케줄러에 걸어 아침마다 돌린다.

REM 한글 출력용 UTF-8 코드페이지
chcp 65001 >nul

title Quant Insight Digest

set "VENV=%~dp0backend\.venv\Scripts\python.exe"
if not exist "%VENV%" (
    echo 가상환경이 없습니다. start.bat 을 한 번 실행해 의존성을 설치하세요.
    pause
    exit /b 1
)

pushd "%~dp0backend"
"%VENV%" -X utf8 -m tools.digest --md --html --open --notify %*
set "CODE=%ERRORLEVEL%"
popd

if not "%CODE%"=="0" (
    echo.
    echo 리포트 생성 실패 ^(종료코드 %CODE%^). 위 메시지를 확인하세요.
    pause
)
exit /b %CODE%
