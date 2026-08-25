@echo off
REM 작업 스케줄러용 digest 실행. 브라우저를 열지 않고 pause 도 하지 않는다.
REM 사람이 볼 때는 digest.bat 을, 자동 실행에는 이 파일을 쓴다.

chcp 65001 >nul

set "VENV=%~dp0backend\.venv\Scripts\python.exe"
if not exist "%VENV%" exit /b 9

pushd "%~dp0backend"
"%VENV%" -X utf8 -m tools.digest --md --html --notify %*
set "CODE=%ERRORLEVEL%"
popd
exit /b %CODE%
