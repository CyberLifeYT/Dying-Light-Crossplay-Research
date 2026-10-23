@echo off
REM Double-click to start the phase-marked Xbox DNS observer (v2). Asks for Administrator rights.
net session >nul 2>&1
if %errorlevel% neq 0 (
    powershell -NoProfile -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
    exit /b
)
title Xbox DNS observer v2
"C:\Users\cyber\AppData\Local\Programs\Python\Python313\python.exe" "%~dp0xbox_dns_phased2.py"
echo.
echo Observer stopped. You can close this window.
pause
