@echo off
REM ============================================================================
REM  capture_xbox.cmd  --  Capture Xbox console network traffic
REM
REM  Right-click -> Run as administrator
REM
REM  This uses netsh trace (built into Windows) since pktmon may not be available
REM  or may have incompatible flags on this version.
REM ============================================================================
setlocal
cd /d "%~dp0"

echo.
echo === Checking for pktmon ===
where pktmon >nul 2>&1
if %errorlevel%==0 (
    echo [+] pktmon found, attempting capture...
    pktmon stop >nul 2>&1
    pktmon filter remove >nul 2>&1
    pktmon start --capture --file-name xbox_trace.etl 2>&1 | findstr /i "started\|success\|error" >nul
    if %errorlevel%==0 (
        echo [+] pktmon capture started
        echo.
        echo === NOW: On the Xbox, start a co-op session and play for 1-2 minutes ===
        echo === Then come back here and press ENTER to stop ===\r
        pause >nul
        pktmon stop >nul 2>&1
        echo [+] Capture stopped
        pktmon etl2pcap xbox_trace.etl --out xbox_trace.pcapng 2>&1 | findstr /i "written\|saved\|error" >nul
        if %errorlevel%==0 (
            echo [+] Converted to xbox_trace.pcapng
            echo.
            echo === Running analysis ===
            python dl_session_probe.py --pcap xbox_trace.pcapng
        ) else (
            echo [!] etl2pcap conversion failed, raw ETL saved at xbox_trace.etl
        )
    ) else (
        echo [!] pktmon start failed
    )
) else (
    echo [-] pktmon not available on this system
    echo.
    echo === Using netsh trace instead ===
    echo Starting netsh trace...
    netsh trace start scenario=NetConnect capture=yes maxSize=256 file=xbox_trace.etl >nul 2>&1
    echo [+] netsh trace started
    echo.
    echo === NOW: On the Xbox, start a co-op session and play for 1-2 minutes ===
    echo === Then press ENTER here to stop ===\r
    pause >nul
    netsh trace stop >nul 2>&1
    echo [+] netsh trace stopped
    echo [+] Saved as xbox_trace.etl
    echo.
    echo === You can also inspect the trace with: netsh trace show scenario ===
)

echo.
echo === Done. If you have a pcapng file, run: ===
echo   python dl_session_probe.py --pcap xbox_trace.pcapng
echo.
pause
