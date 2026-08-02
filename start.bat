@echo off
REM Quant Insight 원클릭 실행
REM 더블클릭하면 백엔드 + 프론트엔드 + 브라우저 자동 기동

REM 한글 출력용 UTF-8 코드페이지
chcp 65001 >nul

title Quant Insight Launcher
powershell -ExecutionPolicy Bypass -NoProfile -File "%~dp0start.ps1"
