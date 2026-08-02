@echo off
chcp 65001 >nul
title Quant Insight Stopper
powershell -ExecutionPolicy Bypass -NoProfile -File "%~dp0stop.ps1"
