@echo off
REM ============================================================================
REM  run_xbox_dns.cmd  --  one-shot launcher for the Xbox console DNS observer
REM
REM  Right-click this file -> "Run as administrator"
REM  (or run it from an Administrator cmd)
REM
REM  It starts the observer on UDP/53 + TCP/53, installs the inbound firewall
REM  rule it needs, and leaves the log at:
REM      C:\Users\cyber\AppData\Local\Temp\opencode\xbox_dns.log
REM ============================================================================
setlocal
cd /d "%~dp0"

echo.
echo === Checking administrator rights ===
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo [X] NOT running as Administrator.
    echo     Port 53 cannot be bound without it.
    echo.
    echo     Right-click this file -^> "Run as administrator", then try again.
    pause
    exit /b 1
)
echo [+] Administrator: OK

echo.
echo === Cleaning up any previous run ===
taskkill /f /im python.exe /fi "WINDOWTITLE eq *xbox_dns*" >nul 2>&1
netsh advfirewall firewall delete rule name="DL-XboxDNS-In-UDP" >nul 2>&1
netsh advfirewall firewall delete rule name="DL-XboxDNS-In-TCP" >nul 2>&1

echo.
echo === Your LAN IPs (use the one on the SAME network as the Xbox) ===
powershell -NoProfile -Command "Get-NetIPAddress -AddressFamily IPv4 | Where-Object { $$_.IPAddress -notlike '127.*' -and $$_.IPAddress -notlike '169.254*' } | ForEach-Object { '    {0}   ({1})' -f $$_.IPAddress, $$_.InterfaceAlias }"

echo.
echo === Starting observer on UDP/53 + TCP/53 ===
echo     Stop it with Ctrl+C when you are done.
echo.
python dl_xbox_dns.py --log xbox_dns.log --no-elevate

echo.
echo === Firewall rule cleanup + results ===
if exist xbox_dns.log (
    echo Log written to %cd%\xbox_dns.log
    echo.
    type xbox_dns.log
) else (
    echo No log was produced.
)
echo.
pause
